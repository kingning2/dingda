"""Graph 执行上下文 — LangChain ChatModel + 步骤进度。

节点通过 ``ctx.llm(prompt)`` 调模型；通过 ``ctx.step(name, status)`` 上报进度
（日志始终打；``on_step`` 可选，供 ``track_workflow.stage`` / UI 使用）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.config import GraphConfig
from agent.graph.model import create_chat_model
from config.settings import AiSettings

logger = logging.getLogger("dingda.graph")

# on_step(step_name, status, *, index, total, label)
StepCallback = Callable[..., None]


class GraphContext:
    """单次 graph invoke 的依赖容器。"""

    def __init__(
        self,
        config: GraphConfig,
        *,
        on_step: StepCallback | None = None,
        steps: tuple[str, ...] = (),
    ) -> None:
        self.config = config
        self.on_step = on_step
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

    def llm(self, user: str, *, system: str | None = None) -> str:
        """节点内简单单轮调用 — 走 LangChain model.invoke。"""
        messages = []
        system_text = system if system is not None else self.config.system
        if system_text:
            messages.append(SystemMessage(content=system_text))
        messages.append(HumanMessage(content=user))
        response = self.model.invoke(messages)
        return str(getattr(response, "content", "") or "")

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
