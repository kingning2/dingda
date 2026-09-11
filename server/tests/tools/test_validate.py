"""validate_selectors Tool：经校验桥在修复现场那一页试跑选择器。"""

from __future__ import annotations

import asyncio

import pytest

from src.crawler.extraction.repair.bridge import ValidationBridge
from src.tools.validate import ValidateInput, ValidateOutput, run_validate


class _Adapter:
    platform = "xianyu"
    section_name = "detail_dom"

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def evaluate_extract(self, page, selectors, *, item_id):
        self.seen.append(item_id)
        return {"title": "商品", "price": "¥12"}


def test_missing_url_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DINGDA_VALIDATE_URL", raising=False)
    out = asyncio.run(run_validate(ValidateInput(selectors={"price": "#p"})))
    assert out == ValidateOutput(error="validate-url-missing")


def test_roundtrip_through_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    """工具 ↔ 桥 打通：工具 POST，桥在宿主页面跑，payload 原样回来。"""
    adapter = _Adapter()

    async def _run() -> ValidateOutput:
        bridge = ValidationBridge(object(), adapter, item_id="7")  # type: ignore[arg-type]
        url = bridge.start()
        try:
            monkeypatch.setenv("DINGDA_VALIDATE_URL", url)
            return await run_validate(
                ValidateInput(selectors={"price": "[class*=price]"})
            )
        finally:
            bridge.stop()

    out = asyncio.run(_run())
    assert out.payload == {"title": "商品", "price": "¥12"}
    assert out.error is None
    assert adapter.seen == ["7"]
