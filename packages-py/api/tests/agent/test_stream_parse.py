"""codex ``exec --json`` 事件映射单测。

样本取自 2026-09-15 实测的 codex-cli 0.152 原始 stdout（``e2e/logs/codex-*.jsonl``），
不是照文档猜的形状 —— 这条链路的坑恰恰在于「文档没说、但实际会发」。

职责：
    锁定 ``_map_codex`` 对 ``item.type`` 的分流：reasoning → thinking、
    agent_message → textDelta、command_execution → toolCall + toolResult。
"""

from __future__ import annotations

from cli.stream import parse_lines


def _events(*lines: str) -> list[dict]:
    return parse_lines("codex-json", "\n".join(lines))


def test_thread_started_becomes_session() -> None:
    events = _events('{"type":"thread.started","thread_id":"01a0a365"}')
    assert events == [{"type": "session", "sessionId": "01a0a365"}]


def test_reasoning_is_thinking_not_text() -> None:
    """推理正文必须走 thinking —— 否则模型的内心独白会被当成给用户的回答。"""
    events = _events(
        '{"type":"item.completed","item":{"id":"item_0","type":"reasoning","text":"We need answer."}}'
    )
    assert events == [{"type": "thinking", "text": "We need answer."}]


def test_agent_message_is_text_delta() -> None:
    events = _events(
        '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"你好"}}'
    )
    assert events == [{"type": "textDelta", "text": "你好"}]


def test_command_execution_yields_tool_call_then_result() -> None:
    """命令执行必须产出 toolCall + toolResult。

    少了它们，工具 stdout 里的商品 JSON 到不了前端，右侧结果面板恒为 0 条 ——
    这正是 2026-09-15 用 codex 跑「找商品」时观察到的症状。
    """
    started = (
        '{"type":"item.started","item":{"id":"item_2","type":"command_execution",'
        '"command":"echo hi","aggregated_output":"","exit_code":null,"status":"in_progress"}}'
    )
    completed = (
        '{"type":"item.completed","item":{"id":"item_2","type":"command_execution",'
        '"command":"echo hi","aggregated_output":"{\\"ok\\":true}","exit_code":0,'
        '"status":"completed"}}'
    )
    events = _events(started, completed)

    assert [event["type"] for event in events] == ["toolCall", "toolResult"]
    assert events[0]["id"] == events[1]["id"] == "item_2"
    assert events[1]["output"] == '{"ok":true}'
    assert events[1]["step"]["status"]["state"] == "ready"
    # 命令原文只留在 input 里给 steps 层用，不进入 step 的展示字段。
    assert "echo hi" not in str(events[1]["step"])


def test_failed_command_execution_marks_error() -> None:
    completed = (
        '{"type":"item.completed","item":{"id":"item_3","type":"command_execution",'
        '"command":"bad","aggregated_output":"boom","exit_code":1,"status":"failed"}}'
    )
    events = _events(completed)
    assert events[0]["type"] == "toolResult"
    assert events[0]["step"]["status"]["state"] == "error"


def test_unknown_and_partial_lines_are_ignored() -> None:
    """未识别的行、非 JSON 行、以及 started 阶段的纯文本 item 都不能炸。"""
    events = _events(
        "not json at all",
        '{"type":"turn.started"}',
        '{"type":"turn.completed","usage":{"input_tokens":1}}',
        '{"type":"item.started","item":{"id":"item_4","type":"agent_message","text":""}}',
    )
    assert events == []
