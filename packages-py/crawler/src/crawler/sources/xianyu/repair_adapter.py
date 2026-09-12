"""闲鱼 detail_dom 修复 adapter。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts.browser_port import Page
from crawler.sources.xianyu import extractor as ex


class XianyuDetailRepairAdapter:
    """闲鱼详情 DOM 修复插头。"""

    platform = "xianyu"
    section_name = "detail_dom"
    extract_beside = Path(ex.__file__)

    def required_fields(self) -> list[str]:
        return ["price", "desc", "want", "seller_nick", "img"]

    def current_selectors(self) -> dict[str, Any]:
        return dict(ex._sec("detail_dom"))

    def dump_roots(self) -> list[str]:
        """dump 根：配置里的主容器 + 卖家区 + body 兜底。

        卖家区 ``item-user-container`` 是 ``item-main-container`` 的兄弟节点，
        只能从 ``body`` 根走；而 ``body → div → content-container → item-container
        → item-user-container → a → item-user-info-container`` 已经第 7 层，
        超过 dump 的 maxDepth=6 —— 昵称/简介元素会被整片截掉。AI 看不到元素，
        就只能退而选那个空壳容器，抽出来的值混进位置、粉丝数、卖出件数等噪音。
        单独当根，它的子树才从浅层展开。
        """
        cfg = self.current_selectors()
        roots = [
            str(cfg[key]).strip()
            for key in ("root", "info")
            if isinstance(cfg.get(key), str) and str(cfg[key]).strip()
        ]
        if not roots:
            roots.append('[class*="item-main-container"]')
        roots.append('[class*="item-user-container"]')
        roots.append("body")
        return roots

    async def evaluate_extract(
        self,
        page: Page,
        selectors: dict[str, Any],
        *,
        item_id: str,
    ) -> dict[str, Any]:
        arg = {
            "itemId": str(item_id),
            "dom": selectors,
            "signals": ex._sec("signals"),
        }
        raw = await page.evaluate(ex.DETAIL_DOM_JS, arg)
        return raw if isinstance(raw, dict) else {"error": "dom-empty"}

    def payload_ok(self, payload: dict[str, Any]) -> bool:
        if payload.get("error"):
            return False
        title = str(payload.get("title") or "").strip()
        return bool(title) and (
            bool(str(payload.get("price") or "").strip())
            or bool(str(payload.get("description") or "").strip())
        )

    def is_risk_payload(self, payload: dict[str, Any]) -> bool:
        return payload.get("error") == "blocked"

    def is_auth_payload(self, payload: dict[str, Any]) -> bool:
        return payload.get("error") == "auth-required"
