"""极简 LangChain tool-call 循环 — 执行侧车工具，把清洗结果回填给模型。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger("dingda.graph.tool_loop")


def run_tool_loop(
    model: BaseChatModel,
    tools: list[BaseTool],
    *,
    system: str,
    user: str,
    max_rounds: int = 4,
    on_tool: Callable[[str, dict[str, Any], str], None] | None = None,
) -> tuple[str, list[BaseMessage]]:
    """跑多轮 tool_calls；返回最终助手文本与完整消息轨迹。

    ponytail: 不引入 AgentExecutor；bind_tools + 手写几轮足够。
    """
    if not tools:
        raise ValueError("tools 不能为空")

    by_name = {t.name: t for t in tools}
    bound = model.bind_tools(tools)
    messages: list[BaseMessage] = [
        SystemMessage(content=system),
        HumanMessage(content=user),
    ]

    final_text = ""
    for round_i in range(1, max_rounds + 1):
        ai = bound.invoke(messages)
        messages.append(ai)
        calls = list(getattr(ai, "tool_calls", None) or [])
        content = str(getattr(ai, "content", "") or "").strip()
        if content:
            final_text = content

        if not calls:
            logger.info("tool_loop.done round=%s no_more_tools", round_i)
            break

        logger.info(
            "tool_loop.round=%s calls=%s",
            round_i,
            [(c.get("name"), c.get("args")) for c in calls],
        )
        for call in calls:
            name = str(call.get("name") or "")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            tool_call_id = str(call.get("id") or name or "tool")
            tool = by_name.get(name)
            if tool is None:
                payload = json.dumps(
                    {"ok": False, "error": f"未知工具: {name}"},
                    ensure_ascii=False,
                )
            else:
                try:
                    raw = tool.invoke(args)
                    payload = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                except Exception as error:  # noqa: BLE001
                    logger.warning("tool_loop.exec_failed name=%s err=%s", name, error)
                    payload = json.dumps(
                        {"ok": False, "error": str(error)[:300]},
                        ensure_ascii=False,
                    )
            if on_tool is not None:
                on_tool(name, dict(args), payload)
            messages.append(ToolMessage(content=payload, tool_call_id=tool_call_id))
    else:
        logger.info("tool_loop.max_rounds=%s", max_rounds)

    if not final_text:
        # 最后一条若是 AI 且无文本，取轨迹里最近的非空 AI content
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                text = str(getattr(msg, "content", "") or "").strip()
                if text:
                    final_text = text
                    break

    return final_text, messages
