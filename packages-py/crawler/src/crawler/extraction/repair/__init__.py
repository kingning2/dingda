"""DOM 修复包。"""

from crawler.extraction.repair.orchestrator import raise_repair_error, repair_detail_dom
from crawler.extraction.repair.types import DomPatch, DomSnapshot, RepairResult

__all__ = [
    "DomPatch",
    "DomSnapshot",
    "RepairResult",
    "raise_repair_error",
    "repair_detail_dom",
]
