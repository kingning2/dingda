"""Headroom compress 单测。

headroom 由 ``core.compress`` 在函数内 ``from headroom import compress`` 惰性导入，
故这里用 ``monkeypatch.setitem(sys.modules, "headroom", ...)`` 注入替身：pytest 会在
用例结束后自动还原，不会把假模块泄漏给同进程的后续用例。
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from core import compress as compress_mod


def _compress_result(content: str, *, saved: int = 10):
    out = MagicMock()
    out.tokens_saved = saved
    out.tokens_before = 100
    out.tokens_after = 100 - saved
    out.messages = [{"role": "user", "content": content}]
    return out


def test_compress_messages_disabled(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    messages = [{"role": "user", "content": "hello"}]
    assert compress_mod.compress_messages(messages) is messages


def test_compress_messages_passthrough_when_headroom_missing(monkeypatch) -> None:
    """headroom 不可导入时透传原文，不外抛。"""
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    monkeypatch.setitem(sys.modules, "headroom", None)
    messages = [{"role": "user", "content": "hello"}]
    assert compress_mod.compress_messages(messages) is messages


def test_compress_messages_uses_headroom(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")

    def fake_compress(messages, *, model="x"):
        return _compress_result("hi")

    monkeypatch.setitem(sys.modules, "headroom", SimpleNamespace(compress=fake_compress))
    result = compress_mod.compress_messages([{"role": "user", "content": "x" * 100}])
    assert result == [{"role": "user", "content": "hi"}]


def test_compress_tool_payload_skips_small(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    payload = {"ok": True, "items": []}
    assert compress_mod.compress_tool_payload(payload, tool_name="search") == payload


def test_compress_text_disabled(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    text = "skill body " * 20
    assert compress_mod.compress_text(text) == text


def test_compress_text_uses_messages(monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")

    def fake_compress(messages, *, model="x"):
        out = MagicMock()
        out.tokens_saved = 1
        out.tokens_before = 10
        out.tokens_after = 9
        out.messages = [{"role": "system", "content": "compressed-skill"}]
        return out

    monkeypatch.setitem(sys.modules, "headroom", SimpleNamespace(compress=fake_compress))
    assert compress_mod.compress_text("long skill text") == "compressed-skill"
