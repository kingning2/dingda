"""浏览器能力层：生命周期、Session、Cookie、导航；不含平台业务。"""

from __future__ import annotations

from src.browser.context import ContextOptions
from src.browser.instance import BrowserInstance, BrowserState
from src.browser.manager import BrowserManager, get_browser_manager
from src.browser.pool import BrowserPool
from src.browser.port import BrowserPort, Cookie, LaunchOptions, Page
from src.browser.registry import create_browser, list_engines
from src.browser.session import BrowserSession
from src.browser.sync import close_sync_browser, sync_headless_page

__all__ = [
    "BrowserManager",
    "BrowserPool",
    "BrowserInstance",
    "BrowserState",
    "get_browser_manager",
    "BrowserPort",
    "BrowserSession",
    "ContextOptions",
    "Cookie",
    "LaunchOptions",
    "Page",
    "create_browser",
    "list_engines",
    "sync_headless_page",
    "close_sync_browser",
]
