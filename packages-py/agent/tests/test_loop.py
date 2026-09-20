"""工具循环：问 → 调工具 → 回填 → 收尾。

这里测的是**循环本身的口径**，不是某个工具的业务：

- 工具出参要原样回到消息里，否则模型下一轮等于瞎了
- 每一步都要有一对 ``toolCall`` / ``toolResult`` —— 少一条前端就永远转圈
- ``stop_tools`` 触发时把参数交出来（修复 agent 就是靠它交选择器的）
- 取消停在**步与步之间**，且不留没收尾的步骤块
- 步数用尽要进不带工具的收尾轮，用户不能看不到总结
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field, PrivateAttr

from agent.context import RunContext
from agent.loop import EXIT_CANCELLED, ToolSpec, build_tools, run_react


class ScriptedChat(BaseChatModel):
    """按脚本顺序应答的假模型。

    自带的 ``GenericFakeChatModel`` 不支持 ``bind_tools``，而循环必须走 bind：
    这里让 ``bind_tools`` 返回自身 —— 工具调用本来就是写在脚本里的。
    """

    script: list[Any] = Field(default_factory=list)
    _cursor: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChat":
        """脚本里写死了 tool_calls，不需要真的绑定。"""
        return self

    def _generate(
        self,
        messages: Any,
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """按游标取下一条应答；脚本用完就停在最后一条。"""
        if not self.script:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])
        index = min(self._cursor, len(self.script) - 1)
        self._cursor += 1
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


class EchoInput(BaseModel):
    """测试工具入参。"""

    value: str = Field(description="原样回传")


async def _echo(ctx: RunContext, value: str) -> dict[str, Any]:
    """把入参原样回传。"""
    return {"ok": True, "value": value}


def _ctx() -> tuple[RunContext, list[dict[str, Any]]]:
    """一个把事件收进列表的上下文。"""
    seen: list[dict[str, Any]] = []

    async def emit(event: dict[str, Any]) -> None:
        seen.append(event)

    return RunContext(run_id="r1", task_id="r1", emit=emit, live=True), seen


def _specs() -> tuple[ToolSpec, ...]:
    """两个工具：一个普通回传，一个作为收尾信号。"""
    return (
        ToolSpec(name="echo", label="回传", description="原样回传", args=EchoInput, fn=_echo),
        ToolSpec(name="finish", label="收尾", description="收尾", args=EchoInput, fn=_echo),
    )


def _llm(*messages: AIMessage) -> ScriptedChat:
    """按给定顺序应答的假模型。"""
    return ScriptedChat(script=list(messages))


def test_tool_result_is_fed_back_and_events_paired() -> None:
    """工具出参进消息、事件成对：这是循环能继续下去的前提。"""
    ctx, seen = _ctx()
    llm = _llm(
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "hi"}, "id": "c1"}]),
        AIMessage(content="收到 hi"),
    )

    result = asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs()),
            messages=[{"role": "user", "content": "叫一声"}],
            ctx=ctx,
            max_steps=4,
        )
    )

    assert result.text == "收到 hi"
    kinds = [event["type"] for event in seen]
    # 一步一工具：toolCall/toolResult 必须成对且顺序相邻，少一条前端就永远转圈
    assert kinds[0] == "toolCall"
    assert kinds[1] == "toolResult"
    # 收尾轮的正文要流式回前端（子 agent 用 stream=False，不会发这条）
    assert kinds[-1] == "textDelta"
    assert seen[1]["output"]["value"] == "hi"
    # toolResult 里必须带回同一个 id，前端靠它把步骤块收尾
    assert seen[0]["id"] == seen[1]["id"]


def test_stop_tool_returns_its_arguments() -> None:
    """收尾工具的参数要交出来：修复 agent 的选择器就是从这里出去的。"""
    ctx, _ = _ctx()
    llm = _llm(
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"value": "好了"}, "id": "c1"}]),
    )

    result = asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs()),
            messages=[{"role": "user", "content": "干活"}],
            ctx=ctx,
            max_steps=4,
            stop_tools=("finish",),
        )
    )

    assert result.stop_name == "finish"
    assert result.stop_args == {"value": "好了"}


def test_cancel_stops_between_steps() -> None:
    """取消后不再开新一步，且事件已经配好对（不留「执行中」的步骤块）。"""
    ctx, seen = _ctx()
    cancel = asyncio.Event()
    cancel.set()
    ctx.cancel = cancel

    llm = _llm(
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "hi"}, "id": "c1"}]),
        AIMessage(content="不该到这"),
    )

    result = asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs()),
            messages=[{"role": "user", "content": "干活"}],
            ctx=ctx,
            max_steps=4,
        )
    )

    assert result.exit_code == EXIT_CANCELLED
    assert seen == []


def test_step_exhaustion_enters_final_round() -> None:
    """步数用尽要再问一轮（不带工具），否则用户看不到总结。"""
    ctx, seen = _ctx()
    llm = _llm(
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "a"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {"value": "b"}, "id": "c2"}]),
        AIMessage(content="总结：a、b"),
    )

    result = asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs()),
            messages=[{"role": "user", "content": "干活"}],
            ctx=ctx,
            max_steps=2,
        )
    )

    assert result.text == "总结：a、b"
    assert result.steps == 2
    assert len([e for e in seen if e["type"] == "toolCall"]) == 2


def test_unknown_tool_is_reported_not_raised() -> None:
    """模型调了不存在的工具：回报错误让它自己纠正，不要把循环炸掉。"""
    ctx, seen = _ctx()
    llm = _llm(
        AIMessage(content="", tool_calls=[{"name": "nope", "args": {}, "id": "c1"}]),
        AIMessage(content="那就算了"),
    )

    result = asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs()),
            messages=[{"role": "user", "content": "干活"}],
            ctx=ctx,
            max_steps=3,
        )
    )

    assert result.text == "那就算了"
    assert seen[1]["output"]["error_code"] == "agent.unknown_tool"


class SummaryInput(BaseModel):
    """带 ``summary`` 的收尾入参，形状照 ``orchestrator.FinishInput``。"""

    summary: str = Field(description="结论")


async def _finish_summary(ctx: RunContext, summary: str) -> dict[str, Any]:
    return {"ok": True, "summary": summary}


def _specs_with_summary() -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(name="echo", label="回传", description="", args=EchoInput, fn=_echo),
        ToolSpec(name="finish", label="收尾", description="", args=SummaryInput, fn=_finish_summary),
    )


def test_stop_tool_summary_is_streamed_when_model_wrote_no_prose() -> None:
    """【回归】结论写在 ``finish`` 的 summary 参里、正文为空时，必须补发成 textDelta。

    收尾工具是 stop_tool，循环命中就立刻返回 —— 不补发的话 ``summary`` 只进
    ``ReactResult``，而 ``run_chat`` 只取 ``exit_code``，结论就此丢掉。实测就是这么
    发生的：用户看到的最后一句停在「我正在更换关键词重新尝试…」，结论一个字都没上去。
    """
    ctx, seen = _ctx()
    llm = _llm(
        AIMessage(
            content="",
            tool_calls=[{"name": "finish", "args": {"summary": "该卖陶瓷马克杯"}, "id": "c1"}],
        ),
    )

    result = asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs_with_summary()),
            messages=[{"role": "user", "content": "我该卖什么"}],
            ctx=ctx,
            max_steps=3,
            stop_tools=("finish",),
        )
    )

    assert [e["text"] for e in seen if e["type"] == "textDelta"] == ["该卖陶瓷马克杯"]
    assert result.text == "该卖陶瓷马克杯"


def test_stop_tool_summary_is_not_duplicated_when_model_wrote_prose() -> None:
    """正文已经写了结论就不要再补一遍，否则用户看到两段一样的话。"""
    ctx, seen = _ctx()
    llm = _llm(
        AIMessage(
            content="我建议卖陶瓷马克杯。",
            tool_calls=[{"name": "finish", "args": {"summary": "该卖陶瓷马克杯"}, "id": "c1"}],
        ),
    )

    asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs_with_summary()),
            messages=[{"role": "user", "content": "我该卖什么"}],
            ctx=ctx,
            max_steps=3,
            stop_tools=("finish",),
        )
    )

    assert [e["text"] for e in seen if e["type"] == "textDelta"] == ["我建议卖陶瓷马克杯。"]


def test_stop_tool_summary_is_not_emitted_for_subagents() -> None:
    """``stream=False`` 的子 agent 不补发 —— 子 agent 的正文是工具结果，推下去会刷屏。"""
    ctx, seen = _ctx()
    llm = _llm(
        AIMessage(
            content="",
            tool_calls=[{"name": "finish", "args": {"summary": "子 agent 的结论"}, "id": "c1"}],
        ),
    )

    asyncio.run(
        run_react(
            llm=llm,
            tools=build_tools(ctx, _specs_with_summary()),
            messages=[{"role": "user", "content": "干活"}],
            ctx=ctx,
            max_steps=3,
            stop_tools=("finish",),
            stream=False,
        )
    )

    assert seen == []
