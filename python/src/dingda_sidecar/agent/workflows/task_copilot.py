"""任务副驾 — LangGraph ReAct 图（AG-UI 事件流经 pipe ``copilot.run`` 推送）。

显式 StateGraph（与比价/买家回复同构）::

    prepare → agent ⇄ tools → END

- ``prepare``：注入任务上下文快照（HumanMessage）
- ``agent``：System prompt + 对话历史，绑定工具调 LLM
- ``tools``：``start_price_compare`` / ``control_run``

``graph.stream(..., stream_mode="messages")`` 产出 token/tool 流，
经 ``_AguiEmitter`` 翻译为 AG-UI 子集 → ``emit_event(copilot.run)`` → Rust → 前端。
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, ToolMessage

from dingda_sidecar.agent.graph.state import CopilotGraphState
from dingda_sidecar.runtime.observability import track_workflow

logger = logging.getLogger("dingda.agent.task_copilot")

COPILOT_RUN_EVENT = "copilot.run"

COPILOT_GRAPH_STEPS: tuple[str, ...] = ("prepare", "agent", "tools")

SYSTEM_PROMPT = """你是钉达（DingDa）选品平台的任务管理副驾。
你帮助用户管理比价任务：回答任务状态与进度、解读比价分析结论、按需求发起新的比价任务、暂停/恢复/取消任务。

规则：
- 用简体中文简洁回答，避免冗长寒暄。
- 任务列表与当前任务详情由系统消息中的「任务上下文快照」提供，引用它回答进度/状态/结论问题；
  快照可能滞后，必要时说明。
- 用户描述了明确的比价需求时，调用 start_price_compare 发起任务，并把返回的 run_id 告知用户。
- 用户要求暂停/继续/取消任务时，调用 control_run。
- 不要编造任务数据；快照中没有的信息就如实说明。"""


# ---------------------------------------------------------------------------
# 运行对象与会话注册表（会话级，不持久化）
# ---------------------------------------------------------------------------


@dataclass
class CopilotRun:
    """一次副驾对话轮。

    ``sink`` 接收 AG-UI 事件 dict（pipe 模式经 ``emit_event(copilot.run)``）；
    ``done`` 在本轮结束（含失败/取消）后置位，供 SSE 写循环退出。
    """

    run_id: str
    thread_id: str
    messages: list[BaseMessage] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    settings_api_key: str = ""
    settings_base_url: str = ""
    settings_model: str = ""
    sink: Callable[[dict[str, Any]], None] = lambda _event: None
    cancelled: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)


_registry_lock = threading.Lock()
_registry: dict[str, CopilotRun] = {}


def register_run(run: CopilotRun) -> None:
    with _registry_lock:
        if len(_registry) > 64:
            for old in list(_registry)[:-64]:
                _registry.pop(old, None)
        _registry[run.run_id] = run


def get_run(run_id: str) -> CopilotRun | None:
    with _registry_lock:
        return _registry.get(run_id)


def remove_run(run_id: str) -> None:
    with _registry_lock:
        _registry.pop(run_id, None)


def make_pipe_sink() -> Callable[[dict[str, Any]], None]:
    """产品路径：经 pipe Event ``copilot.run`` 推送 AG-UI 事件。"""
    from dingda_sidecar.runtime.ipc_push import emit_event

    def _sink(event: dict[str, Any]) -> None:
        emit_event(COPILOT_RUN_EVENT, event)

    return _sink


def _build_tools(default: dict[str, str], run_id: str) -> list[Any]:
    from langchain_core.tools import tool

    from dingda_sidecar.runtime.langgraph.handlers import (
        handle_agent_run_control,
        handle_agent_run_start,
    )

    @tool
    def start_price_compare(query: str) -> str:
        """发起新的比价任务。query 传入用户要比价的商品或需求描述。返回包含 run_id 的 JSON。"""
        result = handle_agent_run_start(
            {
                "user": query,
                "default_base_url": default.get("base_url", ""),
                "default_api_key": default.get("api_key", ""),
                "default_model": default.get("model", ""),
            },
            trace_id=run_id,
        )
        return json.dumps(result, ensure_ascii=False)

    @tool
    def control_run(run_id: str, action: str) -> str:
        """控制比价任务。
        action 取值：pause（暂停）/ continue（继续）/ cancel（取消）/ restart（重启）。
        run_id 为任务 id。
        """
        result = handle_agent_run_control(
            {"run_id": run_id, "action": action},
            trace_id=run_id,
        )
        return json.dumps(result, ensure_ascii=False)

    return [start_price_compare, control_run]


# ---------------------------------------------------------------------------
# LangGraph 编译
# ---------------------------------------------------------------------------


def _compile_copilot_graph(model: Any, tools: list[Any]) -> Any:
    """编译副驾 ReAct 图：prepare → agent ⇄ tools。"""
    from langchain_core.messages import SystemMessage
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import ToolNode, tools_condition

    bound_model = model.bind_tools(tools)

    def prepare_node(state: CopilotGraphState) -> dict[str, Any]:
        if state.get("context_injected"):
            return {}
        ctx = state.get("task_context") or {}
        return {
            "messages": [HumanMessage(content=_context_message(ctx))],
            "context_injected": True,
        }

    def agent_node(state: CopilotGraphState) -> dict[str, Any]:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        response = bound_model.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(CopilotGraphState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "agent")
    graph.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "agent")
    return graph.compile()


# ---------------------------------------------------------------------------
# AG-UI 事件发射器
# ---------------------------------------------------------------------------


class _AguiEmitter:
    def __init__(self, run: CopilotRun) -> None:
        self._run = run

    def emit(self, **fields: Any) -> None:
        event = {"thread_id": self._run.thread_id, "run_id": self._run.run_id, **fields}
        self._run.sink(event)

    def run_started(self) -> None:
        self.emit(type="RUN_STARTED")

    def text_start(self, message_id: str) -> None:
        self.emit(type="TEXT_MESSAGE_START", message_id=message_id, role="assistant")

    def text_content(self, message_id: str, delta: str) -> None:
        self.emit(type="TEXT_MESSAGE_CONTENT", message_id=message_id, delta=delta)

    def text_end(self, message_id: str) -> None:
        self.emit(type="TEXT_MESSAGE_END", message_id=message_id)

    def reasoning_start(self, message_id: str) -> None:
        self.emit(type="REASONING_MESSAGE_START", message_id=message_id, role="assistant")

    def reasoning_content(self, message_id: str, delta: str) -> None:
        self.emit(type="REASONING_MESSAGE_CONTENT", message_id=message_id, delta=delta)

    def reasoning_end(self, message_id: str) -> None:
        self.emit(type="REASONING_MESSAGE_END", message_id=message_id)

    def tool_start(self, tool_call_id: str, tool_name: str) -> None:
        self.emit(type="TOOL_CALL_START", tool_call_id=tool_call_id, tool_name=tool_name)

    def tool_args(self, tool_call_id: str, args_delta: str) -> None:
        self.emit(type="TOOL_CALL_ARGS", tool_call_id=tool_call_id, args_delta=args_delta)

    def tool_end(self, tool_call_id: str) -> None:
        self.emit(type="TOOL_CALL_END", tool_call_id=tool_call_id)

    def tool_result(self, tool_call_id: str, content: str) -> None:
        self.emit(
            type="TOOL_CALL_RESULT",
            message_id=tool_call_id,
            tool_call_id=tool_call_id,
            content=content,
            role="tool",
        )

    def finished(self) -> None:
        self.emit(type="RUN_FINISHED")

    def error(self, message: str, code: str = "copilot_error") -> None:
        self.emit(type="RUN_ERROR", message=message[:500], code=code)


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------


def _context_message(state: dict[str, Any]) -> str:
    lines: list[str] = ["【任务上下文快照（可能滞后）】"]
    tasks = state.get("tasks")
    if isinstance(tasks, list) and tasks:
        lines.append("任务列表：")
        lines.append(json.dumps(tasks, ensure_ascii=False))
    current = state.get("current_run")
    if isinstance(current, dict) and current:
        lines.append("当前任务详情：")
        lines.append(json.dumps(current, ensure_ascii=False))
    if len(lines) == 1:
        lines.append("（暂无任务数据）")
    return "\n".join(lines)


def run_copilot_run(run: CopilotRun) -> None:
    """在 worker 线程执行一轮副驾对话，经 ``run.sink`` 产出 AG-UI 事件流。"""

    def _target() -> None:
        with track_workflow("copilot_run", detail=run.run_id) as tracked:
            tracked.stage("running")
            _execute(run)
            tracked.stage("finished")

    threading.Thread(target=_target, name=f"copilot-run-{run.run_id[:8]}", daemon=True).start()


def _execute(run: CopilotRun) -> None:
    emitter = _AguiEmitter(run)
    emitter.run_started()
    try:
        from dingda_sidecar.agent.graph.model import create_chat_model
        from dingda_sidecar.config.settings import AiSettings

        if not (run.settings_api_key and run.settings_model):
            emitter.error("AI 账号未配置，请先在设置 → AI 中添加账号", code="no_ai_account")
            return

        settings = AiSettings(
            api_key=run.settings_api_key,
            base_url=run.settings_base_url,
            model_name=run.settings_model,
            ai_enabled=True,
        )
        model = create_chat_model(settings)
        tools = _build_tools(
            {
                "base_url": run.settings_base_url,
                "api_key": run.settings_api_key,
                "model": run.settings_model,
            },
            run.run_id,
        )
        compiled = _compile_copilot_graph(model, tools)
        initial: CopilotGraphState = {
            "messages": list(run.messages),
            "task_context": run.state,
            "context_injected": False,
        }

        _stream_graph(compiled, initial, run, emitter)
        emitter.finished()
    except Exception as error:  # noqa: BLE001
        logger.exception("copilot run crashed run_id=%s", run.run_id)
        emitter.error(str(error))
    finally:
        remove_run(run.run_id)
        run.done.set()


def _extract_text_parts(chunk: AIMessageChunk) -> tuple[str, str]:
    """从 AIMessageChunk 拆分 reasoning 与正文（兼容 DeepSeek / 方舟 reasoning_content）。"""
    reasoning = ""
    content = ""
    extra = getattr(chunk, "additional_kwargs", None) or {}
    if isinstance(extra, dict):
        reasoning = str(extra.get("reasoning_content") or extra.get("reasoning") or "")

    raw = chunk.content
    if isinstance(raw, str):
        content = raw
    elif isinstance(raw, list):
        for block in raw:
            if isinstance(block, str):
                content += block
            elif isinstance(block, dict):
                block_type = block.get("type")
                if block_type in ("reasoning", "thinking"):
                    reasoning += str(block.get("text") or block.get("reasoning") or "")
                elif block_type == "text":
                    content += str(block.get("text") or "")
    return reasoning, content


def _stream_graph(
    graph: Any,
    initial: CopilotGraphState,
    run: CopilotRun,
    emitter: _AguiEmitter,
) -> None:
    """消费 LangGraph ``stream_mode="messages"``，翻译为 AG-UI 事件。"""
    message_id = ""
    message_open = False
    reasoning_id = ""
    reasoning_open = False
    open_tools: dict[str, bool] = {}

    def close_text() -> None:
        nonlocal message_open
        if message_open:
            emitter.text_end(message_id)
            message_open = False

    def close_reasoning() -> None:
        nonlocal reasoning_open
        if reasoning_open:
            emitter.reasoning_end(reasoning_id)
            reasoning_open = False

    def close_open_messages() -> None:
        close_text()
        close_reasoning()

    for chunk, _meta in graph.stream(initial, stream_mode="messages"):
        if run.cancelled.is_set():
            break

        if isinstance(chunk, ToolMessage):
            tool_call_id = str(chunk.tool_call_id or "")
            if tool_call_id:
                close_open_messages()
                if open_tools.pop(tool_call_id, False):
                    emitter.tool_end(tool_call_id)
                emitter.tool_result(
                    tool_call_id,
                    chunk.content
                    if isinstance(chunk.content, str)
                    else json.dumps(chunk.content, ensure_ascii=False),
                )
            continue

        if not isinstance(chunk, AIMessageChunk):
            continue

        for call in chunk.tool_call_chunks:
            call_id = str(call.get("id") or "")
            if call_id and call_id not in open_tools:
                close_open_messages()
                open_tools[call_id] = True
                emitter.tool_start(call_id, str(call.get("name") or ""))
            args_delta = call.get("args")
            if call_id and isinstance(args_delta, str) and args_delta:
                emitter.tool_args(call_id, args_delta)

        reasoning_delta, text_delta = _extract_text_parts(chunk)
        if reasoning_delta:
            if not reasoning_open:
                close_text()
                reasoning_id = uuid.uuid4().hex
                emitter.reasoning_start(reasoning_id)
                reasoning_open = True
            emitter.reasoning_content(reasoning_id, reasoning_delta)

        if text_delta:
            if not message_open:
                close_reasoning()
                message_id = uuid.uuid4().hex
                emitter.text_start(message_id)
                message_open = True
            emitter.text_content(message_id, text_delta)

    close_open_messages()
    for tool_call_id in open_tools:
        emitter.tool_end(tool_call_id)
