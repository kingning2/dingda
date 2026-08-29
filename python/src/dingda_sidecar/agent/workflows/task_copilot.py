"""任务副驾 — CopilotKit 对话 agent（AG-UI 事件流）。

与比价六节点可控图不同：本工作流是对话式 ReAct agent，
每轮消费前端直连（SSE 端点 /v1/copilot/agui）请求体的对话历史 + 任务上下文快照，
以 AG-UI 事件子集（见 contracts/schema/v1/copilot/AG_UI_MAPPING.md）
经 sink 回调产出事件帧（HTTP 模式写入 SSE 队列）。

服务端工具::

    start_price_compare  发起比价任务（复用 /v1/agent/run/start 全链路）
    control_run          暂停/继续/取消/重启比价任务（复用 run_control）

任务列表 / 详情由前端经 state 快照注入，不在此处持久化。
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
from langgraph.prebuilt import create_react_agent

from dingda_sidecar.runtime.observability import track_workflow

logger = logging.getLogger("dingda.agent.task_copilot")

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

    ``sink`` 接收 AG-UI 事件 dict（HTTP SSE 模式为队列 put）；
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
        # 同会话旧轮自然过期，防泄漏；上限兜底。
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


# ---------------------------------------------------------------------------
# 服务端工具
# ---------------------------------------------------------------------------


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

    def tool_start(self, tool_call_id: str, tool_name: str) -> None:
        self.emit(type="TOOL_CALL_START", tool_call_id=tool_call_id, tool_name=tool_name)

    def tool_args(self, tool_call_id: str, args_delta: str) -> None:
        self.emit(type="TOOL_CALL_ARGS", tool_call_id=tool_call_id, args_delta=args_delta)

    def tool_end(self, tool_call_id: str) -> None:
        self.emit(type="TOOL_CALL_END", tool_call_id=tool_call_id)

    def tool_result(self, tool_call_id: str, content: str) -> None:
        self.emit(type="TOOL_CALL_RESULT", tool_call_id=tool_call_id, content=content)

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
        agent = create_react_agent(model, tools=tools, state_modifier=SYSTEM_PROMPT)
        input_messages: list[BaseMessage] = [
            *run.messages,
            HumanMessage(content=_context_message(run.state)),
        ]

        _stream(agent, input_messages, run, emitter)
        emitter.finished()
    except Exception as error:  # noqa: BLE001
        logger.exception("copilot run crashed run_id=%s", run.run_id)
        emitter.error(str(error))
    finally:
        remove_run(run.run_id)
        run.done.set()


def _stream(
    agent: Any,
    input_messages: list[BaseMessage],
    run: CopilotRun,
    emitter: _AguiEmitter,
) -> None:
    """消费 ``stream_mode="messages"``，翻译为 AG-UI 事件。"""
    message_id = ""
    message_open = False
    open_tools: dict[str, bool] = {}

    for chunk, _meta in agent.stream(
        {"messages": input_messages},
        stream_mode="messages",
    ):
        if run.cancelled.is_set():
            break

        if isinstance(chunk, ToolMessage):
            tool_call_id = str(chunk.tool_call_id or "")
            if tool_call_id:
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
                if message_open:
                    emitter.text_end(message_id)
                    message_open = False
                open_tools[call_id] = True
                emitter.tool_start(call_id, str(call.get("name") or ""))
            args_delta = call.get("args")
            if call_id and isinstance(args_delta, str) and args_delta:
                emitter.tool_args(call_id, args_delta)

        text = chunk.content if isinstance(chunk.content, str) else ""
        if text:
            if not message_open:
                message_id = uuid.uuid4().hex
                emitter.text_start(message_id)
                message_open = True
            emitter.text_content(message_id, text)

    if message_open:
        emitter.text_end(message_id)
    for tool_call_id in open_tools:
        emitter.tool_end(tool_call_id)
