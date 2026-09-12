"""外部 CLI stdout → AgentEvent。

职责：
    解析 Codex / Claude / OpenCode JSON 行，产出与前端契约对齐的事件 dict。
"""

from __future__ import annotations

import json
from typing import Any

from cli.steps import step_for_tool_call, step_for_tool_result


def parse_lines(
    format_id: str,
    chunk: str,
    *,
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """把一段 stdout 拆成事件列表。

    ``state`` 可选：OpenCode 用其去重 ``session``（键 ``session_id``）。
    """
    events: list[dict[str, Any]] = []
    for line in chunk.splitlines():
        text = line.strip()
        if not text:
            continue
        if format_id == "plain":
            events.append({"type": "textDelta", "text": text + "\n"})
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        if format_id == "claude-stream-json":
            events.extend(_map_claude(value))
        elif format_id == "opencode-json":
            events.extend(_map_opencode(value, state=state))
        else:
            events.extend(_map_codex(value))
    return events


def _map_codex(value: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    event_type = str(value.get("type") or "")
    if event_type == "thread.started":
        thread_id = value.get("thread_id") or value.get("threadId") or ""
        if thread_id:
            out.append({"type": "session", "sessionId": str(thread_id)})
    elif event_type in {"item.completed", "message"}:
        item = value.get("item") if isinstance(value.get("item"), dict) else {}
        text = item.get("text") if isinstance(item, dict) else None
        if isinstance(text, str) and text:
            out.append({"type": "textDelta", "text": text})
        msg = value.get("message") if isinstance(value.get("message"), dict) else {}
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, str) and content:
            out.append({"type": "textDelta", "text": content})
    elif event_type in {"response.output_text.delta", "response.reasoning_summary_text.delta"}:
        delta = value.get("delta")
        if isinstance(delta, str) and delta:
            if "reasoning" in event_type:
                out.append({"type": "thinking", "text": delta})
            else:
                out.append({"type": "textDelta", "text": delta})
    elif event_type in {"tool_call", "function_call", "item.tool_call"}:
        call_id = str(
            value.get("id")
            or value.get("call_id")
            or (value.get("item") or {}).get("call_id")
            or ""
        ).strip()
        name = str(
            value.get("name")
            or (value.get("function") or {}).get("name")
            or (value.get("item") or {}).get("name")
            or ""
        ).strip()
        if not call_id or not name:
            return out
        raw_input = value.get("arguments") or value.get("input") or (value.get("item") or {}).get("input")
        if isinstance(raw_input, str):
            try:
                raw_input = json.loads(raw_input)
            except json.JSONDecodeError:
                pass
        out.append(
            {
                "type": "toolCall",
                "id": call_id,
                "name": name,
                "input": raw_input,
                "step": step_for_tool_call(call_id, name, raw_input),
            }
        )
    elif event_type in {"tool_result", "function_call_output", "item.tool_result"}:
        call_id = str(value.get("id") or value.get("call_id") or "").strip()
        if not call_id:
            return out
        output = value.get("output") or value.get("result") or value.get("content")
        out.append(
            {
                "type": "toolResult",
                "id": call_id,
                "output": output,
                "step": step_for_tool_result(call_id, output),
            }
        )
    elif event_type == "error":
        message = value.get("message") or value.get("error")
        if message:
            out.append({"type": "error", "message": str(message)})
    return out


def _map_claude(value: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    event_type = str(value.get("type") or "")
    if event_type == "assistant":
        message = value.get("message") if isinstance(value.get("message"), dict) else value
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text" and isinstance(block.get("text"), str):
                    out.append({"type": "textDelta", "text": block["text"]})
                elif btype == "tool_use":
                    call_id = str(block.get("id") or "").strip()
                    name = str(block.get("name") or "").strip()
                    if not call_id or not name:
                        continue
                    out.append(
                        {
                            "type": "toolCall",
                            "id": call_id,
                            "name": name,
                            "input": block.get("input"),
                            "step": step_for_tool_call(call_id, name, block.get("input")),
                        }
                    )
        elif isinstance(content, str) and content:
            out.append({"type": "textDelta", "text": content})
    elif event_type == "content_block_delta":
        delta = value.get("delta") if isinstance(value.get("delta"), dict) else {}
        text = delta.get("text") if isinstance(delta, dict) else None
        if isinstance(text, str) and text:
            out.append({"type": "textDelta", "text": text})
    elif event_type == "user":
        message = value.get("message") if isinstance(value.get("message"), dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    call_id = str(block.get("tool_use_id") or "").strip()
                    if not call_id:
                        continue
                    out.append(
                        {
                            "type": "toolResult",
                            "id": call_id,
                            "output": block.get("content"),
                            "step": step_for_tool_result(call_id, block.get("content")),
                        }
                    )
    elif event_type == "error":
        out.append({"type": "error", "message": str(value.get("error") or value)})
    return out


def _map_opencode(
    value: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """对齐原 Tauri ``parsers/opencode.rs``。

    OpenCode 的 ``text`` / ``reasoning`` 事件里 ``part.text`` 往往是**整段快照**
   （每次变长），不是 delta；需相对上次内容切片，否则前端会整块闪现。
    ``part_delta`` 才是真增量。
    """
    out: list[dict[str, Any]] = []
    session_id = (
        value.get("sessionID")
        or value.get("session_id")
        or value.get("sessionId")
        or ""
    )
    if isinstance(session_id, str) and session_id.strip():
        sid = session_id.strip()
        if state is None or state.get("session_id") != sid:
            if state is not None:
                state["session_id"] = sid
            out.append({"type": "session", "sessionId": sid})

    event_type = str(value.get("type") or "")
    if event_type == "text":
        part = value.get("part") if isinstance(value.get("part"), dict) else {}
        text = part.get("text") if isinstance(part, dict) else None
        if isinstance(text, str) and text:
            delta = _opencode_snapshot_delta(state, "text", part, text)
            if delta:
                out.append({"type": "textDelta", "text": delta})
    elif event_type == "reasoning":
        part = value.get("part") if isinstance(value.get("part"), dict) else {}
        text = part.get("text") if isinstance(part, dict) else None
        if isinstance(text, str) and text:
            delta = _opencode_snapshot_delta(state, "reasoning", part, text)
            if delta:
                out.append({"type": "thinking", "text": delta})
    elif event_type == "part_delta":
        delta = value.get("delta")
        if not isinstance(delta, str) or not delta:
            return out
        part_type = str(
            value.get("partType") or value.get("part_type") or "text"
        ).strip()
        # 与快照路径共用游标，避免随后的 full part 再吐一遍
        if state is not None:
            part_id = str(
                value.get("partID")
                or value.get("part_id")
                or value.get("id")
                or part_type
                or "part"
            )
            key = f"opencode:{part_type}:{part_id}"
            state[key] = f"{state.get(key) or ''}{delta}"
        if part_type == "reasoning":
            out.append({"type": "thinking", "text": delta})
        else:
            out.append({"type": "textDelta", "text": delta})
    elif event_type == "tool_use":
        part = value.get("part") if isinstance(value.get("part"), dict) else value
        if not isinstance(part, dict):
            return out
        call_id = str(
            part.get("callID") or part.get("call_id") or part.get("id") or ""
        ).strip()
        name = str(part.get("tool") or "tool").strip() or "tool"
        if not call_id:
            return out
        state_obj = part.get("state") if isinstance(part.get("state"), dict) else {}
        raw_input = state_obj.get("input") if isinstance(state_obj, dict) else None
        status = str(state_obj.get("status") or "").strip().lower() if isinstance(state_obj, dict) else ""
        out.append(
            {
                "type": "toolCall",
                "id": call_id,
                "name": name,
                "input": raw_input,
                "step": step_for_tool_call(call_id, name, raw_input),
            }
        )
        # OpenCode 在 completed/error 时才发 tool_use；error 时常只有 state.error 无 output
        if status in {"completed", "error"} or (
            isinstance(state_obj, dict) and ("output" in state_obj or "error" in state_obj)
        ):
            output = None
            if isinstance(state_obj, dict):
                if "output" in state_obj:
                    output = state_obj.get("output")
                elif "error" in state_obj:
                    output = state_obj.get("error")
            if isinstance(output, str):
                try:
                    parsed = json.loads(output)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    output = parsed
            ok = status != "error"
            if isinstance(output, dict) and output.get("ok") is False:
                ok = False
            out.append(
                {
                    "type": "toolResult",
                    "id": call_id,
                    "output": output,
                    "step": step_for_tool_result(call_id, output, ok=ok),
                }
            )
    elif event_type == "error":
        err = value.get("error") if isinstance(value.get("error"), dict) else {}
        message = (
            (err.get("data") or {}).get("message")
            if isinstance(err.get("data"), dict)
            else None
        )
        if not message:
            message = err.get("message") if isinstance(err, dict) else None
        if not message:
            message = value.get("message")
        out.append({"type": "error", "message": str(message or "OpenCode 执行失败")})
    elif event_type in {"step_start", "step_finish"}:
        pass
    return out


def _opencode_snapshot_delta(
    state: dict[str, Any] | None,
    kind: str,
    part: dict[str, Any],
    text: str,
) -> str:
    """把 OpenCode 快照文本收成相对上次的增量。"""
    part_id = str(part.get("id") or part.get("messageID") or kind)
    key = f"opencode:{kind}:{part_id}"
    prev = ""
    if state is not None:
        prev = str(state.get(key) or "")
    if text == prev:
        return ""
    if not prev:
        delta = text
    elif text.startswith(prev):
        delta = text[len(prev) :]
    else:
        # 非前缀扩展无法安全切片，跳过避免重复堆叠
        if state is not None:
            state[key] = text
        return ""
    if state is not None:
        state[key] = text
    return delta
