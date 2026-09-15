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


def _tool_result(content: str):
    out = MagicMock()
    out.tokens_saved = 100
    out.tokens_before = 500
    out.tokens_after = 400
    out.messages = [{"role": "tool", "tool_call_id": "call_dingda", "content": content}]
    return out


def test_compress_tool_payload_restores_identity_fields(monkeypatch) -> None:
    """【回归】压缩把长字符串换成 ``<<ccr:...>>`` 占位符后，身份字段必须还原。

    工具 stdout 同时是**前端解析商品用的机器契约**：2026-09-15 实测 `search` 返回的
    3 条商品 `title` 全变成 ``<<ccr:8150d6b866ad,string,499B>>``，症状是抓取成功、
    聊天里也有商品，结果面板却恒为 0 条。正文大字段可以压，身份字段不能。
    """
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    payload = {
        "ok": True,
        "platform": "xianyu",
        "items": [
            {
                "item_id": "1067057484474",
                "title": "【8.99元一把包邮】户外折叠椅月亮椅",
                "price": "¥8.90",
                "location": "江苏",
                "desc": "正文占位" * 700,
            }
        ],
    }

    def fake_compress(messages, *, model="x"):
        import json

        raw = json.loads(messages[-1]["content"])
        for item in raw["items"]:
            item["title"] = "<<ccr:8150d6b866ad,string,499B>>"
            item["desc"] = "<<ccr:deadbeef,string,2KB>>"
        return _tool_result(json.dumps(raw, ensure_ascii=False))

    monkeypatch.setitem(sys.modules, "headroom", SimpleNamespace(compress=fake_compress))
    out = compress_mod.compress_tool_payload(payload, tool_name="search")

    item = out["items"][0]
    assert item["title"] == "【8.99元一把包邮】户外折叠椅月亮椅"
    assert item["item_id"] == "1067057484474"
    assert item["price"] == "¥8.90"
    assert item["location"] == "江苏"
    # 正文仍是被压过的占位符 —— 压缩的 token 收益要保住
    assert item["desc"] == "<<ccr:deadbeef,string,2KB>>"


def test_compress_tool_payload_tolerates_structure_change(monkeypatch) -> None:
    """压缩把条目数改了时，还原退化为「不还原」，不抛错也不丢整体结构。"""
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    payload = {
        "ok": True,
        "platform": "xianyu",
        "items": [{"item_id": "1", "title": "A", "desc": "x" * 5000}],
    }

    def fake_compress(messages, *, model="x"):
        import json

        return _tool_result(json.dumps({"ok": True, "platform": "xianyu", "items": []}))

    monkeypatch.setitem(sys.modules, "headroom", SimpleNamespace(compress=fake_compress))
    out = compress_mod.compress_tool_payload(payload, tool_name="search")
    assert out["items"] == []
