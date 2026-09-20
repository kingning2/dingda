"""集成测试专用脚本模型夹具。"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field, PrivateAttr

from agent.context import RunContext


class ScriptedChat(BaseChatModel):
    """按脚本顺序应答的假模型。"""

    script: list[Any] = Field(default_factory=list)
    _cursor: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChat":
        """脚本里写死 tool_calls，不需要真的绑定。"""
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


class FakeLlm:
    """对齐 ``LlmClient``：循环只认 ``.chat_model``。"""

    def __init__(self, model: ScriptedChat) -> None:
        self.chat_model = model


def make_ctx(**kwargs: Any) -> RunContext:
    """拼一个离线 RunContext。"""
    return RunContext(
        run_id="r1",
        task_id="r1",
        llm=kwargs.get("llm"),
        cancel=kwargs.get("cancel") or asyncio.Event(),
    )
