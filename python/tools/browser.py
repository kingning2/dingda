"""浏览器工具 — Playwright 能力探测（登录/搜索走 crawlers）。

``browser_available`` 仅探测运行时是否可导入 Playwright，不负责业务会话。"""

from __future__ import annotations


def browser_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False
