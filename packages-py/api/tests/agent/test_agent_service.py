"""AgentService 工具循环单测。

``AgentService.run`` 的三个可测缝全部在 ``agent.core.agent`` 模块命名空间里，
monkeypatch 即可注入替身，不碰真 LLM 与真工具：

    - ``_llm_client``        → 脚本化假客户端（按轮次弹出响应）
    - ``compress_messages``  → 恒等（不引入 headroom 依赖）
    - ``call_tool`` / ``list_tools`` → 假工具注册表

包内无 pytest-asyncio，用 ``asyncio.run`` 消费异步生成器。
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

import domains.agent.service as agent_mod
from domains.agent.service import AgentService
from core.errors import AppError


# ── 替身构造 ───────────────────────────────────────────────────────────────────

class _FakeSpec(BaseModel):
    """假工具入参模型，供 list_tools().input_model.model_json_schema() 使用。"""

    keyword: str = ""


def _msg(content: str | None, tool_calls: list[Any] | None = None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _resp(content: str | None = None, tool_calls: list[Any] | None = None):
    return SimpleNamespace(choices=[SimpleNamespace(message=_msg(content, tool_calls))])


def _tool_call(call_id: str = "call_1", name: str = "search", arguments: str = '{"keyword": "露营椅"}'):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeClient:
    """按脚本逐轮弹出响应；脚本耗尽后复用最后一项（配合 max-rounds 用例）。"""

    def __init__(self, responses: list[Any], *, error: Exception | None = None) -> None:
        self._responses = list(responses)
        self._error = error
        self.calls: list[dict[str, Any]] = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    async def _create(self, **kwargs: Any) -> Any:
        # 快照消息列表：to_send 与内部 messages 是同一对象（恒等压缩时），事后查看会被后续轮次污染
        self.calls.append({**kwargs, "messages": [dict(m) for m in kwargs.get("messages", [])]})
        if self._error is not None:
            raise self._error
        if not self._responses:
            raise AssertionError("脚本响应耗尽")
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_LLM_API_KEY", "test-key")
    monkeypatch.delenv("DINGDA_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DINGDA_LLM_MODEL", raising=False)


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch, fake_env: None):
    """注入假客户端与恒等压缩；返回 FakeClient 供断言。"""

    def _install(client: FakeClient) -> FakeClient:
        monkeypatch.setattr(agent_mod, "_llm_client", lambda: client)
        monkeypatch.setattr(agent_mod, "compress_messages", lambda messages, *, model: messages)
        return client

    return _install


@pytest.fixture
def fake_tools(monkeypatch: pytest.MonkeyPatch):
    """注入假注册表；call_tool 行为由用例内 rewire。"""

    spec = SimpleNamespace(name="search", description="搜品", input_model=_FakeSpec)
    monkeypatch.setattr(agent_mod, "list_tools", lambda: [spec])
    mock = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"ok": True, "items": []}))
    monkeypatch.setattr(agent_mod, "call_tool", mock)
    return mock


def _collect(**kwargs: Any) -> list[dict[str, Any]]:
    async def _run() -> list[dict[str, Any]]:
        return [event async for event in AgentService().run(**kwargs)]

    return asyncio.run(_run())


def _types(events: list[dict[str, Any]]) -> list[str]:
    return [e["type"] for e in events]


# ── 用例 ───────────────────────────────────────────────────────────────────────

def test_empty_prompt_yields_error_without_run_started() -> None:
    """空 prompt：不发 runStarted，直接 error + runCompleted(1)，且不碰 LLM。"""
    events = _collect(prompt="   ")
    assert _types(events) == ["error", "runCompleted"]
    assert events[-1]["exitCode"] == 1


def test_plain_answer_completes_with_text_delta(fake_llm, fake_tools) -> None:
    """无工具调用的直答：runStarted → textDelta → runCompleted(0)，只调一轮 LLM。"""
    client = fake_llm(FakeClient([_resp(content="你好")]))
    events = _collect(prompt="在吗")

    assert _types(events) == ["runStarted", "textDelta", "runCompleted"]
    assert events[0]["runId"].startswith("run-")
    assert events[-1]["exitCode"] == 0
    assert len(client.calls) == 1
    sent = client.calls[0]["messages"]
    assert sent[0]["role"] == "system"
    assert sent[1] == {"role": "user", "content": "在吗"}


def test_tool_call_roundtrip_appends_tool_message(fake_llm, fake_tools) -> None:
    """一轮工具调用：toolCall/toolResult 事件成对，tool 消息按 json 落回上下文。"""
    client = fake_llm(
        FakeClient([_resp(tool_calls=[_tool_call()]), _resp(content="答案")])
    )
    events = _collect(prompt="搜露营椅")

    assert _types(events) == ["runStarted", "toolCall", "toolResult", "textDelta", "runCompleted"]
    assert events[1] == {"type": "toolCall", "id": "call_1", "name": "search", "input": {"keyword": "露营椅"}}
    assert events[2]["output"] == {"ok": True, "items": []}
    fake_tools.assert_awaited_once_with("search", {"keyword": "露营椅"})

    sent = client.calls[1]["messages"]
    tool_msg = sent[-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_1"
    assert json.loads(tool_msg["content"]) == {"ok": True, "items": []}


def test_tool_invalid_json_args_fall_back_to_empty(fake_llm, fake_tools) -> None:
    """arguments 不是合法 json 时按空入参调用，不让坏参数打断循环。"""
    fake_llm(FakeClient([_resp(tool_calls=[_tool_call(arguments="{oops")]), _resp(content="好")]))
    events = _collect(prompt="x")
    assert events[1]["input"] == {}
    fake_tools.assert_awaited_once_with("search", {})


def test_tool_apperror_maps_to_payload_and_continues(fake_llm, fake_tools) -> None:
    """AppError → toolResult.ok=False + error_code，循环继续到下一轮直答。"""
    fake_tools.side_effect = AppError("tool.denied", "无权限", status_code=403)
    fake_llm(FakeClient([_resp(tool_calls=[_tool_call()]), _resp(content="完成")]))
    events = _collect(prompt="x")

    assert events[2]["output"] == {"ok": False, "error_code": "tool.denied", "message": "无权限"}
    assert events[-1]["exitCode"] == 0


def test_tool_unexpected_error_maps_to_tool_failed(fake_llm, fake_tools) -> None:
    """非 AppError 异常兜底为 tool.failed，不让工具崩溃杀死整轮。"""
    fake_tools.side_effect = RuntimeError("炸了")
    fake_llm(FakeClient([_resp(tool_calls=[_tool_call()]), _resp(content="完成")]))
    events = _collect(prompt="x")

    assert events[2]["output"]["error_code"] == "tool.failed"
    assert events[-1]["exitCode"] == 0


def test_max_rounds_exceeded_yields_error(monkeypatch, fake_llm, fake_tools) -> None:
    """工具轮次打满仍要工具：error + runCompleted(1)，不再无限循环。"""
    monkeypatch.setattr(agent_mod, "_MAX_ROUNDS", 2)
    fake_llm(FakeClient([_resp(tool_calls=[_tool_call()])]))
    events = _collect(prompt="x")

    # 每轮正常发 toolCall/toolResult 事件对，两轮打满后收 error + runCompleted(1)
    expected = ["runStarted"] + ["toolCall", "toolResult"] * 2 + ["error", "runCompleted"]
    assert _types(events) == expected
    assert events[-2] == {"type": "error", "message": "工具轮次超限"}
    assert events[-1]["exitCode"] == 1


def test_llm_apperror_yields_error_events(fake_llm, fake_tools) -> None:
    """LLM 阶段抛 AppError：error + runCompleted(1)，不向上抛。"""
    fake_llm(FakeClient([], error=AppError("agent.llm", "上游挂了")))
    events = _collect(prompt="x")
    assert _types(events) == ["runStarted", "error", "runCompleted"]
    assert events[1]["message"] == "上游挂了"


def test_missing_llm_key_yields_error_events(monkeypatch, fake_tools) -> None:
    """未配置 LLM key：应发 error + runCompleted(1) 兜底事件，而不是把异常抛出流。

    SSE 消费方（前端 AgentEvent 流）在 runStarted 之后只认事件；此处若直接 raise，
    流会以异常收尾且没有 runCompleted，前端无法收尾。
    """
    monkeypatch.delenv("DINGDA_LLM_API_KEY", raising=False)
    events = _collect(prompt="搜露营椅")
    assert _types(events) == ["runStarted", "error", "runCompleted"]
    assert events[1]["message"].startswith("未配置 DINGDA_LLM_API_KEY")
    assert events[-1]["exitCode"] == 1


def test_llm_client_carries_explicit_timeout(
    fake_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """客户端必须带显式超时与受限重试：SDK 默认 600s 交互产品等不起。"""
    monkeypatch.delenv("DINGDA_LLM_TIMEOUT", raising=False)

    client = agent_mod._llm_client()
    assert client.timeout.connect == 10.0
    assert client.timeout.read == 120.0
    assert client.max_retries == 1

    monkeypatch.setenv("DINGDA_LLM_TIMEOUT", "30")
    assert agent_mod._llm_client().timeout.read == 30.0
