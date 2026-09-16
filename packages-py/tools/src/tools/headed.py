"""采集浏览器的有头模式开关（排障用）。

职责：
    读环境变量 ``DINGDA_CRAWL_HEADED``，决定采集浏览器是否可见。

设计说明：
    - 正常采集一律无头；只有人工排障（想亲眼看到页面打开到哪一步、滑块怎么弹的）
      才需要窗口，故只认环境变量，不进工具契约，也不暴露给 Agent。
    - 与风控恢复那个有头窗口无关：那是另一台独立浏览器
      （见 ``channels/xianyu/risk_recovery.py``）。

使用示例：
    DINGDA_CRAWL_HEADED=1 python -m tools.cli search --platform xianyu --query 露营椅 --limit 3
"""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def headed_enabled() -> bool:
    """是否开有头浏览器。"""
    return (os.getenv("DINGDA_CRAWL_HEADED", "") or "").strip().lower() in _TRUTHY


def headless() -> bool:
    """给 ``LaunchOptions(headless=...)`` 的取值。"""
    return not headed_enabled()
