"""Research Workflow：市场调研与机会分析（骨架）。

经 Tool → Crawler 收集数据，不直接 import Playwright / Camoufox。
由 ``api/research`` 调用本 Workflow。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dingda.agent.workflow.research")


class ResearchWorkflow:
    """调研业务流程入口（骨架）。"""
