"""DOM 修复提议（内置 LLM）：prompt / JSON 抠取 / 字段过滤。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from crawler.extraction.repair import propose as repair_propose
from crawler.extraction.repair.types import DomSnapshot


def _fake_client(content: str) -> tuple[SimpleNamespace, dict[str, Any]]:
    """脚本化假 LLM 客户端；顺带记录 create 的入参。"""
    seen: dict[str, Any] = {}

    async def _create(**kwargs: Any) -> SimpleNamespace:
        seen.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    completions = SimpleNamespace(create=_create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), seen


def _snap(**extra: Any) -> DomSnapshot:
    base: dict[str, Any] = {
        "platform": "xianyu",
        "section": "detail_dom",
        "url": "u",
        "item_id": "1",
        "current_selectors": {"price": "#nope"},
        "tree": {"trees": []},
        "required_fields": ["price"],
    }
    base.update(extra)
    return DomSnapshot(**base)


def test_user_prompt_includes_last_failure() -> None:
    """上一轮的失败现场要出现在 prompt 里；没有失败时不该出现。"""
    without = repair_propose._user_prompt(_snap())
    assert "last_attempt_error=" not in without
    assert "last_attempt_payload=" not in without

    text = repair_propose._user_prompt(
        _snap(last_error="dom-empty", last_payload={"error": "dom-empty"})
    )
    assert "last_attempt_error=dom-empty" in text
    assert '{"error": "dom-empty"}' in text


def test_extract_json_plain() -> None:
    assert repair_propose._extract_json('{"price": "[class*=\\"x\\"]"}') == {
        "price": '[class*="x"]'
    }


def test_extract_json_prose_wrapped() -> None:
    text = (
        "我先看一下结构。\n"
        "```json\n"
        '{"price": "[class*=\\"price\\"]", "desc": "[class*=\\"desc\\"]"}\n'
        "```\n"
        "以上。"
    )
    assert repair_propose._extract_json(text) == {
        "price": '[class*="price"]',
        "desc": '[class*="desc"]',
    }


def test_extract_json_skips_earlier_example_object() -> None:
    text = (
        '比如可以写成 {"price": "#bad"} 这样，\n'
        "但按语义片段更稳：\n"
        '{"price": "[class*=\\"price\\"]"}'
    )
    assert repair_propose._extract_json(text) == {"price": '[class*="price"]'}


def test_extract_json_survives_stray_brace_in_reasoning() -> None:
    text = (
        "输出格式是 { 键值对 }，例如：\n"
        '{"price": "[class*=\\"price\\"]"}'
    )
    assert repair_propose._extract_json(text) == {"price": '[class*="price"]'}


def test_extract_json_prefers_outer_object_when_nested() -> None:
    text = (
        "推理里有个落单的 { 号，\n"
        '{"root": {"tag": "div"}, "price": "[class*=\\"price\\"]"}'
    )
    assert repair_propose._extract_json(text) == {
        "root": {"tag": "div"},
        "price": '[class*="price"]',
    }


def test_extract_json_handles_braces_inside_string() -> None:
    assert repair_propose._extract_json('{"a": "}"}') == {"a": "}"}


def test_extract_json_none_when_absent() -> None:
    assert repair_propose._extract_json("全是散文没有补丁") is None
    assert repair_propose._extract_json("") is None


def test_propose_dom_patch_merges_over_current(monkeypatch: pytest.MonkeyPatch) -> None:
    client, seen = _fake_client(
        '{"price": "[class*=\\"price\\"]", "desc": "[class*=\\"desc\\"]",'
        ' "analysis": "上一轮选到容器了"}'
    )
    monkeypatch.setattr(repair_propose, "_llm_client", lambda: client)
    monkeypatch.setenv("DINGDA_LLM_API_KEY", "test-key")
    snap = DomSnapshot(
        platform="xianyu",
        section="detail_dom",
        url="https://www.goofish.com/item?id=1",
        item_id="1",
        current_selectors={"root": "", "price": "", "desc": "", "want_re": "keep-me"},
        tree={"trees": []},
        required_fields=["price", "desc"],
    )

    patch_ = asyncio.run(repair_propose.propose_dom_patch(snap))

    assert patch_ is not None
    assert patch_.source == "ai"
    assert patch_.section == "detail_dom"
    # 走内置 LLM 的 chat.completions，且温度归零
    assert seen.get("temperature") == 0
    assert patch_.selectors["price"] == '[class*="price"]'
    assert patch_.selectors["desc"] == '[class*="desc"]'
    # 原有非选择器配置保留
    assert patch_.selectors["want_re"] == "keep-me"
    # AI 顺手多吐的键不能进配置
    assert "analysis" not in patch_.selectors


def test_repair_model_prefers_repair_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_DOM_REPAIR_MODEL", "m-repair")
    monkeypatch.setenv("DINGDA_LLM_MODEL", "m-general")
    assert repair_propose._repair_model() == "m-repair"

    monkeypatch.delenv("DINGDA_DOM_REPAIR_MODEL", raising=False)
    assert repair_propose._repair_model() == "m-general"

    monkeypatch.delenv("DINGDA_LLM_MODEL", raising=False)
    assert repair_propose._repair_model() == "gpt-4o"


def test_propose_dom_patch_returns_none_on_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Boom:
        # 属性名照 OpenAI SDK 的形状（client.chat.completions.create），小写非类名风格
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: Any) -> Any:
                    raise RuntimeError("llm 崩了")

    monkeypatch.setattr(repair_propose, "_llm_client", lambda: _Boom())
    snap = _snap()
    assert asyncio.run(repair_propose.propose_dom_patch(snap)) is None


def test_propose_dom_patch_returns_none_on_prose_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _fake_client("这页结构看不出来，全是散文没有补丁。")
    monkeypatch.setattr(repair_propose, "_llm_client", lambda: client)
    assert asyncio.run(repair_propose.propose_dom_patch(_snap())) is None


def test_llm_client_carries_explicit_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """修复链客户端必须带显式超时：SDK 默认 600s 修复链等不起。"""
    monkeypatch.setenv("DINGDA_LLM_API_KEY", "test-key")
    monkeypatch.delenv("DINGDA_LLM_TIMEOUT", raising=False)

    client = repair_propose._llm_client()
    assert client.timeout.connect == 10.0
    assert client.timeout.read == 120.0
    assert client.max_retries == 1

    monkeypatch.setenv("DINGDA_LLM_TIMEOUT", "30")
    assert repair_propose._llm_client().timeout.read == 30.0
