"""DOM 自动修复：类型与平台插座。

职责：
    定义 DomSnapshot / DomPatch / PlatformRepairAdapter，
    供 orchestrator 与闲鱼/小红书 adapter 共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from contracts.browser_port import Page


@dataclass
class DomSnapshot:
    """送给 CLI 的精简页面结构。"""

    platform: str
    section: str
    url: str
    item_id: str
    current_selectors: dict[str, Any]
    tree: dict[str, Any]
    required_fields: list[str] = field(default_factory=list)
    # 上一轮失败的现场：讲清「上次抽出来什么、错在哪」，避免下一轮盲改
    last_error: str | None = None
    last_payload: dict[str, Any] | None = None


@dataclass
class DomPatch:
    """AI 或指纹产出的选择器补丁。"""

    section: str
    selectors: dict[str, Any]
    source: str = "ai"


@dataclass
class RepairResult:
    """修复结果。"""

    ok: bool
    payload: dict[str, Any] | None = None
    patch: DomPatch | None = None
    error: str | None = None


class PlatformRepairAdapter(Protocol):
    """平台 DOM 修复插座。"""

    platform: str
    section_name: str
    extract_beside: str | Path

    def required_fields(self) -> list[str]:
        ...

    def current_selectors(self) -> dict[str, Any]:
        ...

    def dump_roots(self) -> list[str]:
        ...

    async def evaluate_extract(
        self,
        page: Page,
        selectors: dict[str, Any],
        *,
        item_id: str,
    ) -> dict[str, Any]:
        """用候选选择器跑平台抽取脚本，返回与产品一致的 payload。"""

    def payload_ok(self, payload: dict[str, Any]) -> bool:
        ...

    def is_risk_payload(self, payload: dict[str, Any]) -> bool:
        ...

    def is_auth_payload(self, payload: dict[str, Any]) -> bool:
        ...
