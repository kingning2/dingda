"""工具循环：问模型 → 调工具 → 回填 → 再问，直到收尾或步数用尽。

职责：
    提供 ``run_react``（一次带工具的对话循环）与 ``tool_of``（把一个 async 函数包成
    模型看得懂的工具）。主编排与三个子 agent 共用这一份循环。

设计说明：
    - **手写循环而不是图**：这里只有「问 → 调 → 再问」一条线，没有分支与并行，
      引入状态图只会多一层样板。真需要分支时再换图，别提前付这个成本。
    - 每一步入口都查取消：取消停在**步与步之间**，跑了一半的工具不会被硬打断
      （硬断会留下「执行中」的步骤块，前端永远等不到收尾）。
    - 正文是否推给前端由 ``stream`` 决定：只有主编排的正文给用户看，子 agent 的中间
      思考推下去只会刷屏 —— 它们的结论是作为工具结果回到主编排的。
    - 步数用尽进**不带工具的收尾轮**：否则最后一轮拿到工具结果就被截断，
      用户看不到总结。

使用示例：
    result = await run_react(
        llm=client.chat_model,
        tools=tools,
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": task}],
        ctx=ctx,
        max_steps=12,
        stop_tools=("finish",),
    )
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool

from agent.context import RunContext, emit_tool_call, emit_tool_result
from agent.steps import step_label

logger = logging.getLogger("dingda.agent.loop")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CANCELLED = 130


@dataclass
class ReactResult:
    """一次循环的结果。"""

    text: str = ""
    steps: int = 0
    stop_name: str | None = None
    """触发收尾的工具名（``finish`` / ``submit_patch`` 之类）；没触发则为 None。"""
    stop_args: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    """每一步工具的出参，按顺序；子 agent 靠它汇总成果（不靠复述正文）。"""
    exit_code: int = EXIT_OK


@dataclass(frozen=True)
class ToolSpec:
    """一个工具的登记项：模型看 name/description/args，前端看 label/browser/kind。"""

    name: str
    label: str
    """步骤块标题；含 ``{platform}`` 时按入参平台替换。"""
    description: str
    args: type
    """入参 schema（pydantic 模型），同时就是模型看到的参数表。"""
    fn: Any
    """``async fn(ctx, **kwargs) -> dict``。"""
    browser: bool = False
    """会不会开浏览器（决定前端步骤块挂不挂页卡）。"""
    kind: str | None = None
    """覆盖步骤 kind；扫码登录用 ``login``，与浏览器直播页卡分开。"""


def build_tools(ctx: RunContext, specs: Sequence[ToolSpec]) -> list[BaseTool]:
    """按登记项造一批绑定到本次运行的工具。"""
    return [
        tool_of(
            name=spec.name,
            description=spec.description,
            args_schema=spec.args,
            fn=spec.fn,
            ctx=ctx,
            label=spec.label,
            browser=spec.browser,
            kind=spec.kind,
        )
        for spec in specs
    ]


def tool_of(
    *,
    name: str,
    description: str,
    args_schema: type,
    fn: Any,
    ctx: RunContext,
    label: str,
    browser: bool = False,
    kind: str | None = None,
) -> BaseTool:
    """把一个 ``async fn(ctx, **kwargs) -> dict`` 包成模型可调的工具。

    ``label`` / ``browser`` / ``kind`` 只用于前端步骤块，模型不看。
    """
    meta = {"label": label, "browser": browser, "kind": kind}

    async def _run(**kwargs: Any) -> str:
        output = await fn(ctx, **kwargs)
        return json.dumps(output, ensure_ascii=False, default=str)

    tool = StructuredTool.from_function(
        coroutine=_run,
        name=name,
        description=description.strip(),
        args_schema=args_schema,
    )
    # 前端步骤块要中文标题与「挂不挂页卡」，挂在工具对象上随调用一起取用
    tool.metadata = meta  # type: ignore[attr-defined]
    return tool


async def run_react(
    *,
    llm: Any,
    tools: Sequence[BaseTool],
    messages: Sequence[dict[str, Any] | BaseMessage],
    ctx: RunContext,
    max_steps: int = 12,
    stop_tools: Sequence[str] = (),
    stream: bool = True,
) -> ReactResult:
    """跑一次带工具的循环；返回 ``ReactResult``。

    ``messages`` 可以是 dict（``{role, content}``）或 LangChain 消息。
    """
    history = _to_messages(messages)
    bound = llm.bind_tools(list(tools)) if tools else llm
    by_name = {tool.name: tool for tool in tools}
    steps = max(1, max_steps)
    collected: list[dict[str, Any]] = []

    for step in range(1, steps + 1):
        if ctx.cancelled():
            logger.info("循环被取消 run=%s step=%s", ctx.run_id, step)
            return ReactResult(steps=step - 1, tool_results=collected, exit_code=EXIT_CANCELLED)

        message = await _stream_ask(bound, history, ctx=ctx, stream=stream)
        history.append(message)

        calls = list(getattr(message, "tool_calls", None) or ())
        if not calls:
            logger.info("循环自然收尾 run=%s step=%s", ctx.run_id, step)
            return ReactResult(text=_text_of(message), steps=step, tool_results=collected)

        for call in calls:
            name = str(call.get("name") or "")
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            if name in stop_tools:
                logger.info("循环被收尾工具结束 run=%s stop=%s", ctx.run_id, name)
                text = _text_of(message)
                summary = str(args.get("summary") or "").strip()
                if stream and summary and not text.strip():
                    # 模型把结论写进了收尾工具的 `summary` 参而不是正文。不补发的话，
                    # 用户看到的就只有中途的「我正在…」—— 结论随着返回一起被丢掉。
                    # 只在正文为空时补，正常「先写正文再 finish」的路径不会重复播报。
                    logger.info("收尾摘要补发正文 run=%s len=%s", ctx.run_id, len(summary))
                    await ctx.emit_event({"type": "textDelta", "text": summary})
                    text = summary
                return ReactResult(
                    text=text,
                    steps=step,
                    stop_name=name,
                    stop_args=dict(args),
                    tool_results=collected,
                )
            await _invoke(by_name.get(name), name, args, history, ctx=ctx, sink=collected)
            if ctx.cancelled():
                return ReactResult(steps=step, tool_results=collected, exit_code=EXIT_CANCELLED)

    logger.info("步数用尽，进收尾轮 run=%s steps=%s", ctx.run_id, steps)
    final = await _stream_ask(llm, history, ctx=ctx, stream=stream)
    return ReactResult(text=_text_of(final), steps=steps, tool_results=collected)


async def _invoke(
    tool: BaseTool | None,
    name: str,
    args: dict[str, Any],
    history: list[BaseMessage],
    *,
    ctx: RunContext,
    sink: list[dict[str, Any]],
) -> None:
    """调一次工具，把过程发成 ``toolCall`` / ``toolResult`` 并回填消息。"""
    meta = getattr(tool, "metadata", None) or {}
    call_id = ctx.new_call_id(name)
    kind = str(meta["kind"]) if meta.get("kind") else None
    await emit_tool_call(
        ctx,
        call_id=call_id,
        name=name,
        label=step_label(str(meta.get("label") or name), str(args.get("platform") or "")),
        hint=_hint_of(args),
        browser=bool(meta.get("browser")),
        payload=args,
        kind=kind,
    )

    ctx.active_call_id = call_id
    try:
        if tool is None:
            output: dict[str, Any] = {
                "ok": False,
                "error_code": "agent.unknown_tool",
                "message": f"没有这个工具：{name}",
            }
        else:
            try:
                raw = await tool.ainvoke(args)
                output = _as_dict(raw)
            except Exception as exc:  # noqa: BLE001 — 工具的意外不该炸穿循环
                logger.exception("工具异常 name=%s", name)
                output = {"ok": False, "error_code": "agent.tool_failed", "message": str(exc)}
    finally:
        ctx.active_call_id = None

    await emit_tool_result(ctx, call_id=call_id, output=output)
    sink.append({"name": name, "args": args, "output": output})
    history.append(
        ToolMessage(
            content=json.dumps(output, ensure_ascii=False, default=str),
            tool_call_id=call_id,
        )
    )


async def _stream_ask(
    llm: Any,
    messages: list[BaseMessage],
    *,
    ctx: RunContext,
    stream: bool,
) -> AIMessage:
    """流式问一次模型：正文 / 思考边收边发，拼成完整 ``AIMessage``。"""
    assembled: AIMessage | None = None
    async for chunk in llm.astream(messages):
        if not isinstance(chunk, AIMessage):
            continue
        if stream:
            text = _text_of(chunk)
            if text:
                await ctx.emit_event({"type": "textDelta", "text": text})
            reasoning = _reasoning_of(chunk)
            if reasoning:
                await ctx.emit_event({"type": "thinking", "text": reasoning})
        assembled = chunk if assembled is None else assembled + chunk
    return assembled if assembled is not None else AIMessage(content="")


def _to_messages(messages: Sequence[dict[str, Any] | BaseMessage]) -> list[BaseMessage]:
    """dict / BaseMessage → LangChain 消息列表。"""
    out: list[BaseMessage] = []
    for item in messages:
        if isinstance(item, BaseMessage):
            out.append(item)
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def _text_of(message: AIMessage) -> str:
    """``AIMessage.content`` → 纯文本（content 可能是 list of blocks）。"""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return ""


def _reasoning_of(message: AIMessage) -> str:
    """流式 chunk 的思考增量。"""
    bag = message.additional_kwargs if isinstance(message.additional_kwargs, dict) else {}
    for key in ("reasoning_content", "reasoning"):
        value = bag.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _hint_of(args: dict[str, Any]) -> str | None:
    """步骤块标题后那句：挑一个像「在干什么」的入参。"""
    for key in ("query", "item_id", "platform"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}={value.strip()}"[:60]
    return None


def _as_dict(raw: Any) -> dict[str, Any]:
    """工具返回值 → dict；字符串按 JSON 解，解不动就包成 ``{"text": ...}``。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {"ok": True, "text": raw}
        return parsed if isinstance(parsed, dict) else {"ok": True, "text": parsed}
    return {"ok": True, "text": str(raw)}
