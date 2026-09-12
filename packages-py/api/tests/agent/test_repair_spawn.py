"""CLI 输出里抠 JSON 补丁：容忍推理散文 / 花括号 / 多个对象。"""

from __future__ import annotations

import asyncio

import pytest

from cli.repair import propose as repair_spawn
from crawler.extraction.repair.types import DomSnapshot


def test_user_prompt_includes_last_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """上一轮的失败现场要出现在 prompt 里；没有失败时不该出现。"""
    monkeypatch.setenv("DINGDA_DOM_REPAIR_RUNTIME", "codex")
    base: dict[str, object] = {
        "platform": "xianyu",
        "section": "detail_dom",
        "url": "u",
        "item_id": "1",
        "current_selectors": {"price": "#nope"},
        "tree": {"trees": []},
        "required_fields": ["price"],
    }
    without = repair_spawn._user_prompt(DomSnapshot(**base))  # type: ignore[arg-type]
    assert "last_attempt_error=" not in without
    assert "last_attempt_payload=" not in without

    text = repair_spawn._user_prompt(
        DomSnapshot(
            **base,  # type: ignore[arg-type]
            last_error="dom-empty",
            last_payload={"error": "dom-empty"},
        )
    )
    assert "last_attempt_error=dom-empty" in text
    assert '{"error": "dom-empty"}' in text


def test_repair_runtime_follows_user_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    """子 agent 的 runtime/model 跟用户在应用里选的那个走，不硬编码。"""
    from infrastructure.db import settings as settings_repo

    monkeypatch.delenv("DINGDA_DOM_REPAIR_RUNTIME", raising=False)
    monkeypatch.setattr(settings_repo, "get_default_agent_id", lambda: "opencode")
    monkeypatch.setattr(
        settings_repo, "get_default_models", lambda: {"opencode": "openrouter/x:free"}
    )
    assert repair_spawn._repair_runtime() == ("opencode", "openrouter/x:free")


def test_repair_runtime_env_overrides_user_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    from infrastructure.db import settings as settings_repo

    monkeypatch.setenv("DINGDA_DOM_REPAIR_RUNTIME", "claude")
    monkeypatch.setattr(settings_repo, "get_default_agent_id", lambda: "opencode")
    monkeypatch.setattr(settings_repo, "get_default_models", lambda: {"claude": "m1"})
    assert repair_spawn._repair_runtime() == ("claude", "m1")


def test_repair_runtime_without_any_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """设置读不到也得给出一个 runtime，不能抛。"""
    from infrastructure.db import settings as settings_repo

    monkeypatch.delenv("DINGDA_DOM_REPAIR_RUNTIME", raising=False)
    monkeypatch.setattr(settings_repo, "get_default_agent_id", lambda: None)
    monkeypatch.setattr(settings_repo, "get_default_models", lambda: {})
    monkeypatch.setattr(settings_repo, "get_agent_runtimes_catalog", lambda: [])
    runtime, model = repair_spawn._repair_runtime()
    assert runtime in {"codex", "claude", "opencode"}
    assert model is None


def test_extract_json_plain() -> None:
    assert repair_spawn._extract_json('{"price": "[class*=\\"x\\"]"}') == {
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
    assert repair_spawn._extract_json(text) == {
        "price": '[class*="price"]',
        "desc": '[class*="desc"]',
    }


def test_extract_json_skips_earlier_example_object() -> None:
    text = (
        '比如可以写成 {"price": "#bad"} 这样，\n'
        "但按语义片段更稳：\n"
        '{"price": "[class*=\\"price\\"]"}'
    )
    assert repair_spawn._extract_json(text) == {"price": '[class*="price"]'}


def test_extract_json_survives_stray_brace_in_reasoning() -> None:
    text = (
        "输出格式是 { 键值对 }，例如：\n"
        '{"price": "[class*=\\"price\\"]"}'
    )
    assert repair_spawn._extract_json(text) == {"price": '[class*="price"]'}


def test_extract_json_prefers_outer_object_when_nested() -> None:
    text = (
        "推理里有个落单的 { 号，\n"
        '{"root": {"tag": "div"}, "price": "[class*=\\"price\\"]"}'
    )
    assert repair_spawn._extract_json(text) == {
        "root": {"tag": "div"},
        "price": '[class*="price"]',
    }


def test_extract_json_handles_braces_inside_string() -> None:
    assert repair_spawn._extract_json('{"a": "}"}') == {"a": "}"}


def test_extract_json_none_when_absent() -> None:
    assert repair_spawn._extract_json("全是散文没有补丁") is None
    assert repair_spawn._extract_json("") is None


def test_propose_dom_patch_merges_over_current(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, bool] = {}

    async def _fake_cli(runtime: str, prompt: str, *, role=None, mcp_env=None, model_id=None):
        seen["role"] = role
        yield {"type": "thinking", "text": "先看 { 结构，用语义片段更稳。"}
        yield {
            "type": "textDelta",
            "text": (
                '{"price": "[class*=\\"price\\"]", "desc": "[class*=\\"desc\\"]",'
                ' "analysis": "上一轮选到容器了"}'
            ),
        }

    monkeypatch.setattr(repair_spawn, "run_cli", _fake_cli)
    monkeypatch.setenv("DINGDA_DOM_REPAIR_RUNTIME", "codex")
    snap = DomSnapshot(
        platform="xianyu",
        section="detail_dom",
        url="https://www.goofish.com/item?id=1",
        item_id="1",
        current_selectors={"root": "", "price": "", "desc": "", "want_re": "keep-me"},
        tree={"trees": []},
        required_fields=["price", "desc"],
    )

    patch = asyncio.run(repair_spawn.propose_dom_patch(snap))

    assert patch is not None
    assert patch.source == "ai"
    assert patch.section == "detail_dom"
    # 修复子 agent 走「子 agent 角色」：不注入 MCP、不拼父提示词、cwd 隔离
    assert seen["role"] == "child"
    assert patch.selectors["price"] == '[class*="price"]'
    assert patch.selectors["desc"] == '[class*="desc"]'
    # 原有非选择器配置保留
    assert patch.selectors["want_re"] == "keep-me"
    # AI 顺手多吐的键不能进配置
    assert "analysis" not in patch.selectors


def test_child_role_workdir_lives_outside_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """子 agent 的 cwd 必须在仓库外：否则它能读到现成的选择器。"""
    import shutil
    from pathlib import Path

    from cli.roles import child as child_mod

    monkeypatch.setattr(child_mod, "_WORKDIR", None)
    workdir = child_mod.scratch_workdir()
    try:
        assert workdir.is_dir()
        assert "dingda-child-agent-" in workdir.name
        repo = Path(__file__).resolve().parents[2]
        assert workdir != repo
        assert repo not in workdir.parents
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        monkeypatch.setattr(child_mod, "_WORKDIR", None)


def test_session_log_reports_tool_surface() -> None:
    """日志要如实写：工具走 skill 注入、拼不拼父前言。"""
    from cli.base import _mcp_config_line

    narrow = _mcp_config_line(
        "codex-mcp", tools=["validate_selectors"], uses_system_prompt=False
    )
    assert "skill" in narrow
    assert "仅本次 prompt" in narrow
    assert "system.md" not in narrow

    wide = _mcp_config_line("none", uses_system_prompt=True)
    assert "system.md" in wide


def test_propose_dom_patch_returns_none_on_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_cli(runtime: str, prompt: str, *, role=None, mcp_env=None, model_id=None):
        yield {"type": "textDelta", "text": '{"price": "[class*=\\"price\\"]"}'}
        yield {"type": "error", "message": "cli 崩了"}

    monkeypatch.setattr(repair_spawn, "run_cli", _fake_cli)
    monkeypatch.setenv("DINGDA_DOM_REPAIR_RUNTIME", "codex")
    snap = DomSnapshot(
        platform="xianyu",
        section="detail_dom",
        url="u",
        item_id="1",
        current_selectors={"price": ""},
        tree={},
    )
    assert asyncio.run(repair_spawn.propose_dom_patch(snap)) is None
