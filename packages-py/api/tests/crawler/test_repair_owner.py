"""RepairOwner 归属策略单测。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.errors import AppError
from crawler.extraction.repair.owner import (
    EscalateToParent,
    InlineCrawlerRepair,
    RepairContext,
    get_repair_owner,
)
from crawler.extraction.repair.types import RepairResult


def test_get_repair_owner_defaults_to_escalate(monkeypatch) -> None:
    monkeypatch.delenv("DINGDA_REPAIR_OWNER", raising=False)
    assert isinstance(get_repair_owner(), EscalateToParent)
    monkeypatch.setenv("DINGDA_REPAIR_OWNER", "parent")
    assert isinstance(get_repair_owner(), EscalateToParent)
    monkeypatch.setenv("DINGDA_REPAIR_OWNER", "crawler")
    assert isinstance(get_repair_owner(), InlineCrawlerRepair)


def test_escalate_raises_needs_repair() -> None:
    async def _run() -> None:
        adapter = SimpleNamespace(platform="xianyu")
        decision = await EscalateToParent().on_dom_extract_failed(
            RepairContext(
                page=SimpleNamespace(),
                adapter=adapter,  # type: ignore[arg-type]
                item_id="7",
                url="https://example.com",
                platform="xianyu",
            )
        )
        assert decision.action == "escalate"
        assert decision.error is not None
        assert decision.error.code == "crawler.needs_repair"
        assert decision.error.details == {
            "platform": "xianyu",
            "item_id": "7",
            "url": "https://example.com",
        }

    asyncio.run(_run())


def test_inline_calls_repair_detail_dom() -> None:
    async def _run() -> None:
        result = RepairResult(ok=True, payload={"title": "x"})
        with patch(
            "crawler.extraction.repair.orchestrator.repair_detail_dom",
            new=AsyncMock(return_value=result),
        ) as mocked:
            adapter = SimpleNamespace(platform="xianyu")
            decision = await InlineCrawlerRepair().on_dom_extract_failed(
                RepairContext(
                    page=SimpleNamespace(),
                    adapter=adapter,  # type: ignore[arg-type]
                    item_id="7",
                )
            )
            assert decision.action == "inline"
            assert decision.result is result
            mocked.assert_awaited_once()

    asyncio.run(_run())
