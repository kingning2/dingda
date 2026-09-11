"""DOM 修复写盘。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.crawler.extraction.config import write_extract_section
from src.crawler.extraction.repair.types import DomPatch

logger = logging.getLogger("dingda.crawler.repair.persist")


def persist_patch(beside: str | Path, patch: DomPatch) -> dict[str, Any]:
    """把补丁写入 extract.json 对应 section 并热加载。"""
    logger.info(
        "persist patch section=%s source=%s keys=%s",
        patch.section,
        patch.source,
        sorted(patch.selectors.keys())[:16],
    )
    return write_extract_section(beside, patch.section, patch.selectors)
