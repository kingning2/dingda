"""产品 Agent 核心编排。

职责：
    收用户目标 → 经 Tool Registry 选型调用 → Headroom 压缩后调 LLM → 产出事件。
    禁止直连 Playwright / Crawler Source / 平台 Channel。

设计说明：
    - LLM：OpenAI-compatible（``DINGDA_LLM_BASE_URL`` / ``DINGDA_LLM_API_KEY`` / ``DINGDA_LLM_MODEL``）
    - 工具：search / product / compare
    - 事件形对齐前端 AgentEvent（供 SSE）

使用示例：
    async for event in AgentService().run(prompt="搜闲鱼露营椅"):
        ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from src.agent.core.compress import compress_messages
from src.crawler.ocr import warm_ocr
from src.shared.errors import AppError
from src.tools.registry import call_tool, list_tools

logger = logging.getLogger("dingda.agent")

_SYSTEM = """你是叮答选品助手。用工具搜品/拉详情/比价，用中文简短回答。
可用工具见 functions。平台 id：xianyu（闲鱼）、xiaohongshu（小红书）、ali1688（1688）。
闲鱼 / 小红书图文：search 会对返回条目逐条拉详情；小红书优先读 content_text（正文+OCR）。
视频笔记（note_type=video）暂跳过，不要当成已读。禁止只凭列表标题下结论。
不要编造商品；没有工具结果就说明失败原因。"""

_MAX_ROUNDS = 8


def _llm_client() -> AsyncOpenAI:
    api_key = os.getenv("DINGDA_LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AppError(
            "agent.llm_key_missing",
            "未配置 DINGDA_LLM_API_KEY（或 OPENAI_API_KEY）",
            status_code=503,
        )
    base = os.getenv("DINGDA_LLM_BASE_URL", "").strip() or None
    return AsyncOpenAI(api_key=api_key, base_url=base)


def _model_name() -> str:
    return os.getenv("DINGDA_LLM_MODEL", "gpt-4o").strip() or "gpt-4o"


def _openai_tools() -> list[dict[str, Any]]:
    """把 registry Tool 收成 Chat Completions tools。"""
    rows: list[dict[str, Any]] = []
    for spec in list_tools():
        schema = spec.input_model.model_json_schema()
        rows.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": schema,
                },
            }
        )
    return rows


class AgentService:
    """产品 Agent：Tool 循环 + Headroom + OpenAI-compatible。"""

    async def run(
        self,
        prompt: str,
        *,
        run_id: str | None = None,
        runtime_id: str = "dingda",
    ) -> AsyncIterator[dict[str, Any]]:
        """执行一轮对话，yield AgentEvent 形 dict（含 type 字段）。"""
        rid = (run_id or f"run-{uuid.uuid4().hex[:12]}").strip()
        text = (prompt or "").strip()
        if not text:
            yield {"type": "error", "message": "prompt 不能为空"}
            yield {"type": "runCompleted", "exitCode": 1}
            return

        # OCR 仅 Agent 选品图文用：开跑即后台预热，与思考并行
        asyncio.create_task(asyncio.to_thread(warm_ocr))

        logger.info("agent start run=%s runtime=%s", rid, runtime_id)
        yield {"type": "runStarted", "runtimeId": runtime_id, "runId": rid}

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ]
        tools = _openai_tools()
        client = _llm_client()
        model = _model_name()

        try:
            for round_i in range(_MAX_ROUNDS):
                to_send = compress_messages(messages, model=model)
                logger.info("agent llm round=%s messages=%s", round_i + 1, len(to_send))
                response = await client.chat.completions.create(
                    model=model,
                    messages=to_send,  # type: ignore[arg-type]
                    tools=tools,  # type: ignore[arg-type]
                )
                choice = response.choices[0].message
                tool_calls = list(choice.tool_calls or [])

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": choice.content,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ]
                messages.append(assistant_msg)

                if choice.content:
                    yield {"type": "textDelta", "text": choice.content}

                if not tool_calls:
                    yield {"type": "runCompleted", "exitCode": 0}
                    logger.info("agent done run=%s", rid)
                    return

                for tc in tool_calls:
                    name = tc.function.name
                    raw_args = tc.function.arguments or "{}"
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                    if not isinstance(args, dict):
                        args = {}
                    yield {"type": "toolCall", "id": tc.id, "name": name, "input": args}
                    try:
                        out = await call_tool(name, args)
                        payload = out.model_dump() if hasattr(out, "model_dump") else dict(out)
                    except AppError as exc:
                        payload = {"ok": False, "error_code": exc.code, "message": exc.message}
                    except Exception as exc:
                        logger.exception("agent tool failed name=%s", name)
                        payload = {"ok": False, "error_code": "tool.failed", "message": str(exc)}
                    yield {"type": "toolResult", "id": tc.id, "output": payload}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(payload, ensure_ascii=False, default=str),
                        }
                    )

            yield {"type": "error", "message": "工具轮次超限"}
            yield {"type": "runCompleted", "exitCode": 1}
        except AppError as exc:
            logger.warning("agent failed code=%s", exc.code)
            yield {"type": "error", "message": exc.message}
            yield {"type": "runCompleted", "exitCode": 1}
        except Exception as exc:
            logger.exception("agent failed run=%s", rid)
            yield {"type": "error", "message": str(exc)}
            yield {"type": "runCompleted", "exitCode": 1}
