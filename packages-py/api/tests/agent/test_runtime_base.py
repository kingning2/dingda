"""CliRuntime 插座：插头解析 + 压缩方法。"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from cli.base import COMPRESS_MIN_BYTES, CliRuntime
from cli.registry import get_runtime, list_runtime_ids


def test_get_runtime_returns_socket_instance() -> None:
    runtime = get_runtime("codex")
    assert isinstance(runtime, CliRuntime)
    assert runtime.id == "codex"
    assert set(list_runtime_ids()) >= {"codex", "claude", "opencode"}


def test_runtime_unknown_id_raises() -> None:
    with pytest.raises(KeyError):
        get_runtime("nope")


def test_claude_stdin_is_stream_json_message() -> None:
    """claude 的 --input-format stream-json 收 JSON 消息，灌纯文本会报解析错。"""
    import json

    line = json.loads(get_runtime("claude").encode_stdin("你好").decode("utf-8").strip())
    assert line["type"] == "user"
    assert line["message"]["role"] == "user"
    assert line["message"]["content"][0]["text"] == "你好"


def test_other_runtimes_send_plain_stdin() -> None:
    assert get_runtime("codex").encode_stdin("hi") == b"hi"
    assert get_runtime("opencode").encode_stdin("hi") == b"hi"


def test_compress_payload_passthrough_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    payload = {"trees": [{"classes": ["x" * 5000]}]}
    assert get_runtime("codex").compress_payload(payload, label="dom_tree") is payload


def test_compress_payload_skips_small_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    payload = {"a": 1}
    assert get_runtime("codex").compress_payload(payload, label="dom_tree") is payload


def test_compress_payload_uses_headroom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    result = MagicMock()
    result.tokens_saved = 10
    result.tokens_before = 100
    result.tokens_after = 20
    result.messages = [
        {"role": "tool", "tool_call_id": "call_dingda", "content": '{"a": 1}'}
    ]
    monkeypatch.setitem(sys.modules, "headroom", MagicMock(compress=MagicMock(return_value=result)))

    payload = {"trees": [{"classes": ["x" * 5000]}]}
    assert len(str(payload)) > COMPRESS_MIN_BYTES
    assert get_runtime("codex").compress_payload(payload, label="dom_tree") == {"a": 1}


def test_compress_payload_keeps_original_on_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    result = MagicMock()
    result.messages = [
        {"role": "tool", "tool_call_id": "call_dingda", "content": "不是 JSON"}
    ]
    monkeypatch.setitem(sys.modules, "headroom", MagicMock(compress=MagicMock(return_value=result)))

    payload = {"trees": [{"classes": ["x" * 5000]}]}
    assert get_runtime("codex").compress_payload(payload, label="dom_tree") is payload
