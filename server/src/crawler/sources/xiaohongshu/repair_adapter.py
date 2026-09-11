"""小红书 detail_dom 修复 adapter。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.browser.port import Page
from src.crawler.sources.xiaohongshu import extractor as ex


class XiaohongshuDetailRepairAdapter:
    """小红书详情 DOM 修复插头。"""

    platform = "xiaohongshu"
    section_name = "detail_dom"
    extract_beside = Path(ex.__file__)

    def required_fields(self) -> list[str]:
        return ["title", "author", "card"]

    def current_selectors(self) -> dict[str, Any]:
        return dict(ex._sec("detail_dom"))

    def dump_roots(self) -> list[str]:
        cfg = self.current_selectors()
        card = cfg.get("card")
        roots: list[str] = []
        if isinstance(card, str) and card.strip():
            # 取第一个逗号选择器
            roots.append(card.split(",")[0].strip())
        roots.extend(["#noteContainer", ".note-container", "body"])
        return roots

    async def evaluate_extract(
        self,
        page: Page,
        selectors: dict[str, Any],
        *,
        item_id: str,
    ) -> dict[str, Any]:
        arg = {"noteId": str(item_id), "dom": selectors}
        raw = await page.evaluate(ex.DOM_DETAIL_JS, arg)
        return raw if isinstance(raw, dict) else {"ready": False}

    def payload_ok(self, payload: dict[str, Any]) -> bool:
        if not payload.get("ready"):
            return False
        note = payload.get("note")
        if not isinstance(note, dict):
            return False
        return bool(str(note.get("title") or "").strip())

    def is_risk_payload(self, payload: dict[str, Any]) -> bool:
        return bool(payload.get("blocked"))

    def is_auth_payload(self, payload: dict[str, Any]) -> bool:
        return False
