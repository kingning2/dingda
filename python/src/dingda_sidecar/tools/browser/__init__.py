"""tools.browser — 浏览器能力入口（探测实现在 runtimes.browser）。"""

from dingda_sidecar.runtime.browser.runtime import browser_available, browser_status

__all__ = ["browser_available", "browser_status"]
