"""MCP 工具白名单：DINGDA_MCP_TOOLS 决定注册哪些工具。"""

from __future__ import annotations

import pytest

from src.mcp.register import register_internal_tools


class _FakeMCP:
    """收集注册进来的工具名。"""

    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, *, name: str, description: str):
        def _decorator(handler):
            self.names.append(name)
            return handler

        return _decorator


def test_registers_public_tools_without_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DINGDA_MCP_TOOLS", raising=False)
    mcp = _FakeMCP()
    registered = register_internal_tools(mcp)  # type: ignore[arg-type]
    assert "search" in registered
    # 内部工具（修复子 agent 专用）不进默认面
    assert "validate_selectors" not in registered


def test_registers_only_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_MCP_TOOLS", "validate_selectors")
    mcp = _FakeMCP()
    registered = register_internal_tools(mcp)  # type: ignore[arg-type]
    assert registered == ["validate_selectors"]
    assert mcp.names == ["validate_selectors"]


def test_allowlist_ignores_blank_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_MCP_TOOLS", " validate_selectors , ")
    assert register_internal_tools(_FakeMCP()) == ["validate_selectors"]  # type: ignore[arg-type]
