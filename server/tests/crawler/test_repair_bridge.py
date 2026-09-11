"""校验桥：临时监听 + 在宿主页面跑候选选择器。"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from src.crawler.extraction.repair.bridge import ValidationBridge


class _Adapter:
    """记录被喂进来的选择器。"""

    platform = "xianyu"
    section_name = "detail_dom"

    def __init__(self) -> None:
        self.seen: list[dict[str, Any]] = []

    async def evaluate_extract(
        self,
        page: Any,
        selectors: dict[str, Any],
        *,
        item_id: str,
    ) -> dict[str, Any]:
        self.seen.append({"selectors": selectors, "item_id": item_id})
        return {"title": "商品", "price": "¥12"}


def test_bridge_validates_on_host_page() -> None:
    adapter = _Adapter()

    async def _run() -> dict[str, Any]:
        bridge = ValidationBridge(object(), adapter, item_id="7")  # type: ignore[arg-type]
        url = bridge.start()
        try:
            assert url.startswith("http://127.0.0.1:")
            resp = await asyncio.to_thread(
                httpx.post,
                url,
                json={"selectors": {"price": "[class*=price]"}},
                timeout=10,
            )
            return resp.json()
        finally:
            bridge.stop()

    assert asyncio.run(_run()) == {"title": "商品", "price": "¥12"}
    assert adapter.seen == [{"selectors": {"price": "[class*=price]"}, "item_id": "7"}]


def test_bridge_rejects_bad_body() -> None:
    async def _run() -> int:
        bridge = ValidationBridge(object(), _Adapter(), item_id="7")  # type: ignore[arg-type]
        url = bridge.start()
        try:
            resp = await asyncio.to_thread(httpx.post, url, json={"nope": 1}, timeout=10)
            return resp.status_code
        finally:
            bridge.stop()

    assert asyncio.run(_run()) == 400


def test_bridge_url_empty_before_start() -> None:
    bridge = ValidationBridge(object(), _Adapter(), item_id="7")  # type: ignore[arg-type]
    assert bridge.url == ""
    bridge.stop()  # 幂等：没起也能关
