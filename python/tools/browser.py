"""浏览器工具 — Playwright 能力探测（登录/搜索走 crawlers）。"""

from __future__ import annotations


def browser_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False
