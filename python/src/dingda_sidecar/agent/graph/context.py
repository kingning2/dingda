"""Graph 执行上下文 — LangChain ChatModel + 步骤进度。

节点通过 ``ctx.llm(prompt)`` 调模型；通过 ``ctx.step(name, status)`` 上报进度
（日志始终打；``on_step`` 可选，供 ``track_workflow.stage`` / UI 使用）。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from dingda_sidecar.agent.graph.config import GraphConfig
from dingda_sidecar.agent.graph.model import create_chat_model
from dingda_sidecar.config.settings import AiSettings

logger = logging.getLogger("dingda.graph")

StepCallback = Callable[..., None]
LlmDeltaCallback = Callable[[str], None]

_LLM_EMIT_INTERVAL_SEC = 0.02


def _delta_text(chunk: object) -> str:
    """OpenAI SSE / LangChain chunk → 增量文本（含方舟 reasoning_content）。"""
    if isinstance(chunk, dict):
        choices = chunk.get("choices") or []
        if choices:
            delta = choices[0].get("delta") if isinstance(choices[0], dict) else {}
            if isinstance(delta, dict):
                return f"{delta.get('reasoning_content') or ''}{delta.get('content') or ''}"

    choices = getattr(chunk, "choices", None)
    if choices:
        delta = getattr(choices[0], "delta", None)
        if delta is not None:
            reasoning = getattr(delta, "reasoning_content", None) or ""
            content = getattr(delta, "content", None) or ""
            extra = getattr(delta, "model_extra", None) or {}
            if not reasoning and isinstance(extra, dict):
                reasoning = extra.get("reasoning_content") or ""
            return f"{reasoning or ''}{content or ''}"

    extra = getattr(chunk, "additional_kwargs", None) or {}
    reasoning = extra.get("reasoning_content") or extra.get("reasoning") or ""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return f"{reasoning}{content}"
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return f"{reasoning}{''.join(parts)}"
    return f"{reasoning}{content or ''}"


def _to_openai_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in messages:
        role = "system" if isinstance(msg, SystemMessage) else "user"
        out.append({"role": role, "content": str(msg.content)})
    return out


class GraphContext:
    """单次 graph invoke 的依赖容器。"""

    def __init__(
        self,
        config: GraphConfig,
        *,
        on_step: StepCallback | None = None,
        on_llm: LlmDeltaCallback | None = None,
        steps: tuple[str, ...] = (),
    ) -> None:
        self.config = config
        self.on_step = on_step
        self.on_llm = on_llm
        self.steps = steps
        self._model: BaseChatModel | None = None

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            settings = self.config.ai_settings or AiSettings(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                model_name=self.config.model,
            )
            self._model = create_chat_model(settings)
        return self._model

    def _emit_llm(self, text: str) -> None:
        if self.on_llm is not None:
            self.on_llm(text)

    def _pump(self, chunks: Iterable[object]) -> str:
        pieces: list[str] = []
        last_emit = 0.0
        first = True
        for chunk in chunks:
            piece = _delta_text(chunk)
            if not piece:
                continue
            pieces.append(piece)
            if first:
                first = False
                logger.info("graph.llm.first_delta chars=%s", len(piece))
            now = time.monotonic()
            if now - last_emit >= _LLM_EMIT_INTERVAL_SEC:
                last_emit = now
                self._emit_llm("".join(pieces))
        acc = "".join(pieces)
        if acc:
            self._emit_llm(acc)
        return acc

    def _openai_stream(self, messages: list[BaseMessage]) -> str | None:
        """直连 ChatOpenAI.client.create(stream=True)，避开 LangChain 丢掉 reasoning。"""
        create = getattr(getattr(self.model, "client", None), "create", None)
        if create is None:
            return None
        model_name = (
            getattr(self.model, "model_name", None)
            or getattr(self.model, "model", None)
            or self.config.model
        )
        try:
            stream = create(
                model=str(model_name),
                messages=_to_openai_messages(messages),
                stream=True,
                temperature=0.5,
                max_tokens=8192,
            )
        except Exception:  # noqa: BLE001
            logger.exception("openai SSE 创建失败，回退 LangChain stream")
            return None
        return self._pump(stream)

    def llm(self, user: str, *, system: str | None = None) -> str:
        """节点内单轮调用 — 优先 OpenAI SSE，再 LangChain stream，最后 invoke。"""
        messages: list[BaseMessage] = []
        system_text = system if system is not None else self.config.system
        if system_text:
            messages.append(SystemMessage(content=system_text))
        messages.append(HumanMessage(content=user))

        acc = self._openai_stream(messages)
        if acc:
            return acc

        try:
            acc = self._pump(self.model.stream(messages))
            if acc:
                return acc
        except Exception:  # noqa: BLE001
            logger.exception("LangChain stream 失败，回退 invoke")

        response = self.model.invoke(messages)
        acc = str(getattr(response, "content", "") or "")
        self._emit_llm(acc)
        return acc

    def step(self, name: str, status: str = "running", *, detail: str = "") -> None:
        """上报当前节点进度。status: running | done | error。"""
        total = len(self.steps)
        try:
            index = self.steps.index(name) + 1 if self.steps else 0
        except ValueError:
            index = 0
        label = f"{index}/{total} {name}" if total and index else name
        logger.info(
            "graph step=%s status=%s label=%s detail=%s",
            name,
            status,
            label,
            detail or "-",
            extra={
                "feature": "graph",
                "step": name,
                "step_status": status,
                "step_label": label,
            },
        )
        if self.on_step is not None:
            self.on_step(name, status, index=index, total=total, label=label, detail=detail)
