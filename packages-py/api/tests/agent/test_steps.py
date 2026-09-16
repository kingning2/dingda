"""steps 形状单测。"""

from __future__ import annotations

import json

from cli.steps import (
    normalize_tool_name,
    page_from_live_frame,
    step_for_tool_call,
    step_for_tool_result,
)


def test_preview_tool_is_browser_crawl() -> None:
    step = step_for_tool_call("c1", "preview", {"url": "https://example.com"})
    assert step["kind"] == "browser_crawl"
    assert step["page"]["url"] == "https://example.com"
    assert step["page"]["loading"] is True


def test_search_tool_is_browser_crawl_with_platform_label() -> None:
    step = step_for_tool_call(
        "c2",
        "dingda_search",
        {"platform": "xianyu", "query": "椅"},
    )
    assert step["kind"] == "browser_crawl"
    assert step["label"] == "搜索商品 · 闲鱼"
    assert step["page"]["loading"] is True
    assert step["page"]["focus_label"] == "搜索「椅」"


def test_shell_tool_recovers_dingda_call_from_bare_bin() -> None:
    """skill 注入后业务工具藏在 shell 命令里，要还原成结构化工具。"""
    step = step_for_tool_call(
        "c3",
        "command_execution",
        {"command": 'tool search --platform xianyu --query "露营椅" --limit 30'},
    )
    assert step["label"] == "搜索商品 · 闲鱼"
    assert step["kind"] == "browser_crawl"
    assert step["page"]["focus_label"] == "搜索「露营椅」"


def test_shell_tool_recovers_old_entries_and_hyphen_flags() -> None:
    """未重装 skill 的机器上仍是旧入口，也要认。"""
    cases = (
        (
            '"C:\\py.exe" ".dingda-skills/dingda-crawl/scripts/run_tool.py" '
            'search --platform xianyu --query "露营椅" --limit 30',
            "搜索商品 · 闲鱼",
            "搜索「露营椅」",
        ),
        (
            "python -m tools.cli product --platform xianyu --item-id 733352707833",
            "查看商品详情 · 闲鱼",
            "详情 733352707833",
        ),
        (
            "C:/x/.venv/Scripts/tool.exe browse --platform xiaohongshu --query 露营",
            "连贯浏览",
            "浏览「露营」",
        ),
    )
    for command, label, focus in cases:
        step = step_for_tool_call("c6", "command_execution", {"command": command})
        assert step["label"] == label
        assert step["page"]["focus_label"] == focus


def test_shell_tool_recovers_through_powershell_wrapper() -> None:
    """codex 在 Windows 上把命令包进 ``powershell.exe -Command '…'``，闭引号不闭合。

    实测命令（2026-09-15 e2e）：外层 ``-Command`` 的 ``'`` 让 POSIX 分词抛
    ``No closing quotation``，以前一抛就放弃还原，界面上退回「执行操作」。
    """
    raw = (
        '"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" '
        "-Command 'tool search --platform xianyu --query \"露营椅\" --limit 20'"
    )
    step = step_for_tool_call("c10", "command_execution", {"command": raw})
    assert step["label"] == "搜索商品 · 闲鱼"
    assert step["kind"] == "browser_crawl"
    assert step["page"]["focus_label"] == "搜索「露营椅」"
    assert step["command"] == raw


def test_shell_command_lands_only_in_the_collapsed_field() -> None:
    """命令原文只进 command 字段（折叠区），不许渗进标题 / 说明 / 页卡文案。"""
    step = step_for_tool_call(
        "c7",
        "command_execution",
        {"command": 'tool search --platform xianyu --query "椅"'},
    )
    assert step["command"] == 'tool search --platform xianyu --query "椅"'
    visible = {key: value for key, value in step.items() if key != "command"}
    assert "tool" not in json.dumps(visible, ensure_ascii=False)


def test_shell_tool_without_dingda_call_stays_opaque() -> None:
    """与业务无关的命令仍只显示「执行操作」，不还原、不挂页卡。"""
    for name in ("command_execution", "bash", "shell"):
        step = step_for_tool_call(name, name, {"command": "git status --short"})
        assert step["label"] == "执行操作"
        assert step["hint"] is None
        assert step["kind"] == "tool"
        assert step["command"] == "git status --short"


def test_shell_tool_recovery_bails_on_unusable_subcommand() -> None:
    """``--help`` / 未知子命令还原不出工具，退回「执行操作」。"""
    for command in (
        '"C:\\py.exe" ".dingda-skills/dingda-crawl/scripts/run_tool.py" --help',
        '"C:\\py.exe" ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --help',
        "tool search --help",
        "tool deploy --force",
        "rm -rf .dingda-skills",
    ):
        step = step_for_tool_call("c4", "command_execution", {"command": command})
        assert step["label"] == "执行操作"
        assert step["kind"] == "tool"


def test_file_tool_is_not_parsed_as_command() -> None:
    """文件类工具的入参里也可能出现 ``tool search``，不能当命令还原。"""
    step = step_for_tool_call(
        "c5",
        "read",
        {"command": 'tool search --platform xianyu --query "椅"'},
    )
    assert step["label"] == "读取资料"
    assert step["hint"] is None
    assert "command" not in step


def test_tool_result_carries_full_output_without_truncating() -> None:
    """折叠区要看到全文，不能像 hint 那样截到 160 字。"""
    raw = "行内容\n" * 500
    patch = step_for_tool_result("c8", raw)
    assert patch["output"] == raw


def test_tool_result_structures_dict_output_as_json() -> None:
    patch = step_for_tool_result("c9", {"ok": True, "items": [{"item_id": "1"}]})
    assert json.loads(patch["output"])["items"][0]["item_id"] == "1"


def test_read_tool_never_leaks_file_content() -> None:
    """读取类工具的输入是文件内容，绝不能出现在步骤文案里。"""
    step = step_for_tool_call("read", "read", "<path>D:\\x\\run_tool.py</path> <content>1: secret")
    assert step["label"] == "读取资料"
    assert step["hint"] is None


def test_tool_result_raw_text_is_not_shown() -> None:
    """原始 stdout / 报错原文（非结构化）不得渲染给用户。"""
    patch = step_for_tool_result("c1", "所在位置 行:1 字符: 46 + ... python.exe\" ...run_tool.py")
    assert patch["hint"] is None


def test_tool_result_structured_error_still_shown() -> None:
    """结构化错误（message / error_code）仍要露出来 —— 那是给用户看的。"""
    patch = step_for_tool_result("c1", {"ok": False, "error_code": "login.timeout"})
    assert patch["status"]["state"] == "error"
    assert patch["hint"] == "login.timeout"


def test_normalize_strips_tool_prefix() -> None:
    assert normalize_tool_name("goofish_search") == "search"
    assert normalize_tool_name("dingda_product") == "product"
    assert normalize_tool_name("search") == "search"


def test_tool_result_ok_false_is_error() -> None:
    patch = step_for_tool_result(
        "c1",
        {"ok": False, "error_code": "account.session_expired", "message": "请扫码"},
        ok=True,
    )
    assert patch["status"]["state"] == "error"
    assert patch["hint"] == "请扫码"


def test_tool_result_and_page() -> None:
    patch = step_for_tool_result("c1", {"ok": True})
    assert patch["status"]["state"] == "ready"
    assert patch["page_loading"] is False
    page = page_from_live_frame(
        url="https://a",
        title="t",
        hint="直播中",
        screenshot_url="data:image/jpeg;base64,xx",
    )
    assert page["screenshot_url"].startswith("data:")
