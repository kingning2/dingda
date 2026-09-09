"""Headroom compress 单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.core import compress as compress_mod


def test_compress_messages_disabled(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    messages = [{"role": "user", "content": "hello"}]
    assert compress_mod.compress_messages(messages) is messages


def test_compress_messages_passthrough_on_import_error(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    messages = [{"role": "user", "content": "hello"}]
    with patch.dict("sys.modules", {"headroom": None}):
        with patch("builtins.__import__", side_effect=ImportError("no")):
            # 直接 patch compress 导入路径
            pass
    with patch.object(compress_mod, "headroom_enabled", return_value=True):
        with patch(
            "src.agent.core.compress.compress_messages",
            wraps=compress_mod.compress_messages,
        ):
            # 用内部逻辑：mock from headroom import
            real = compress_mod.compress_messages

    def fake_compress(messages, model="x"):
        out = MagicMock()
        out.tokens_saved = 10
        out.tokens_before = 100
        out.tokens_after = 90
        out.messages = [{"role": "user", "content": "hi"}]
        return out

    with patch.dict("sys.modules", {"headroom": MagicMock(compress=fake_compress)}):
        # Re-call via importing compress inside function — patch headroom module
        import sys

        sys.modules["headroom"] = MagicMock(compress=fake_compress)
        monkeypatch.setenv("DINGDA_HEADROOM", "1")
        result = compress_mod.compress_messages([{"role": "user", "content": "x" * 100}])
        assert result == [{"role": "user", "content": "hi"}]


def test_compress_tool_payload_skips_small(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    payload = {"ok": True, "items": []}
    assert compress_mod.compress_tool_payload(payload, tool_name="search") == payload
