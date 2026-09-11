"""DOM 修复与抓取恢复接线单测（不启浏览器 / 不调 AI）。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from src.crawler.core.recovery_hooks import run_step
from src.crawler.extraction import fingerprint as fp
from src.crawler.extraction.repair.orchestrator import repair_detail_dom
from src.crawler.extraction.repair.types import RepairResult
from src.shared.errors import AppError, risk_control_error


class _FakeRisk:
    """记录调用次数的风控恢复插座。"""

    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls = 0
        self._fail_times = fail_times

    async def recover_risk(self, page: Any, *, where: str, url: str | None = None) -> None:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise risk_control_error(f"{where} 人工超时")


def test_run_step_retries_after_risk_recovery() -> None:
    async def _run() -> None:
        attempts = {"n": 0}
        risk = _FakeRisk()

        async def _body() -> str:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise risk_control_error("首页风控")
            return "ok"

        out = await run_step("x.search", _body, page=object(), risk=risk)
        assert out == "ok"
        assert attempts["n"] == 2
        assert risk.calls == 1

    asyncio.run(_run())


def test_run_step_gives_up_after_max_retries() -> None:
    async def _run() -> None:
        risk = _FakeRisk()

        async def _body() -> str:
            raise risk_control_error("一直风控")

        try:
            await run_step("x.search", _body, page=object(), risk=risk, max_retries=2)
        except AppError as exc:
            assert exc.code == "channel.risk"
        else:  # pragma: no cover - 应抛异常
            raise AssertionError("预期抛 channel.risk")
        assert risk.calls == 2

    asyncio.run(_run())


def test_xhs_needs_repair_covers_missing_author() -> None:
    """作者空过也要触发修复；否则选择器烂掉会静默出空数据。"""
    from src.crawler.core.types import CrawlItem
    from src.crawler.sources.xiaohongshu.crawler import _needs_repair

    def _item(title: str, nick: str) -> CrawlItem:
        return CrawlItem(
            item_id="n1",
            title=title,
            url="https://www.xiaohongshu.com/explore/n1",
            price=None,
            raw={"seller_nick": nick},
        )

    assert _needs_repair(None) is True
    assert _needs_repair(_item("", "作者")) is True
    assert _needs_repair(_item("标题", "")) is True
    assert _needs_repair(_item("标题", "作者")) is False


def test_xianyu_dump_roots_cover_seller_region() -> None:
    """卖家区必须单独当 dump 根：从 body 数下来会超过 maxDepth，昵称会被截掉。"""
    from src.crawler.sources.xianyu.repair_adapter import XianyuDetailRepairAdapter

    roots = XianyuDetailRepairAdapter().dump_roots()
    assert any("item-user-container" in root for root in roots)
    assert roots[-1] == "body"


def test_repair_feeds_last_failure_into_next_round(tmp_path: Path) -> None:
    """上一轮失败的选择器 + 实际抽到的内容，要一起传给下一轮，不能盲改。"""
    from src.crawler.extraction.repair.types import DomPatch

    extract = tmp_path / "extract.json"
    extract.write_text(
        json.dumps({"detail_dom": {"title": "#t", "price": "#p"}}),
        encoding="utf-8",
    )
    adapter = _FakeAdapter(extract)
    dump = {
        "url": "https://www.goofish.com/item?id=7",
        "preview": "商品 正文",
        "trees": [],
    }
    page = SimpleNamespace(url=dump["url"], evaluate=AsyncMock(return_value=dump))
    snaps: list[Any] = []

    async def _propose(snap: Any, *, validate_url: str | None = None) -> DomPatch:
        snaps.append(snap)
        pick = "#nope" if len(snaps) == 1 else "[class*=price]"
        return DomPatch(
            section="detail_dom",
            selectors={**snap.current_selectors, "price": pick},
            source="ai",
        )

    async def _run() -> RepairResult:
        with (
            patch("src.crawler.extraction.fingerprint._STORE", tmp_path / "fp.json"),
            patch(
                "src.crawler.extraction.repair.orchestrator.relocate_section",
                return_value=None,
            ),
            patch("src.cli.repair.propose.propose_dom_patch", _propose),
        ):
            return await repair_detail_dom(page, adapter, item_id="7")

    result = asyncio.run(_run())

    assert result.ok is True
    assert len(snaps) == 2
    # 第一轮没有失败现场可给
    assert snaps[0].last_error is None
    assert snaps[0].last_payload is None
    # 第二轮带上了「上次抽出来是 dom-empty」
    assert snaps[1].last_error == "dom-empty"
    assert snaps[1].last_payload == {"error": "dom-empty"}


class _FakeAdapter:
    """最小 PlatformRepairAdapter：首次选择器不中用，靠指纹重定位。"""

    platform = "xianyu"
    section_name = "detail_dom"

    def __init__(self, beside: Path) -> None:
        self.extract_beside = str(beside)
        self.payload: dict[str, Any] = {}

    def required_fields(self) -> list[str]:
        return ["title", "price"]

    def current_selectors(self) -> dict[str, Any]:
        return {"title": "#stale-title", "price": "#stale-price"}

    def dump_roots(self) -> list[str]:
        return ["body"]

    async def evaluate_extract(
        self,
        page: Any,
        selectors: dict[str, Any],
        *,
        item_id: str,
    ) -> dict[str, Any]:
        if "price" in str(selectors.get("price") or ""):
            return {"title": f"商品{item_id}", "price": "¥12"}
        return {"error": "dom-empty"}

    def payload_ok(self, payload: dict[str, Any]) -> bool:
        return bool(payload.get("title")) and not payload.get("error")

    def is_risk_payload(self, payload: dict[str, Any]) -> bool:
        return payload.get("error") == "blocked"

    def is_auth_payload(self, payload: dict[str, Any]) -> bool:
        return payload.get("error") == "auth-required"


def test_repair_survives_invalid_selector(tmp_path: Path) -> None:
    """模型吐非 CSS 伪类（:has-text）时只能算这轮没抽到，不能把抓取带崩。"""
    from unittest.mock import AsyncMock as _AsyncMock

    extract = tmp_path / "extract.json"
    extract.write_text(
        json.dumps({"detail_dom": {"title": "#t", "price": "#p"}}),
        encoding="utf-8",
    )

    class _RaisingAdapter(_FakeAdapter):
        async def evaluate_extract(self, page, selectors, *, item_id):  # type: ignore[override]
            raise ValueError("'[class*=price]:has-text(\"1\")' is not a valid selector")

    adapter = _RaisingAdapter(extract)
    dump = {"url": "u", "preview": "商品 正文", "trees": []}
    page = SimpleNamespace(url="u", evaluate=AsyncMock(return_value=dump))

    async def _run() -> RepairResult:
        with (
            patch("src.crawler.extraction.fingerprint._STORE", tmp_path / "fp.json"),
            patch(
                "src.crawler.extraction.repair.orchestrator.relocate_section",
                return_value={"title": "[class*=t]", "price": "[class*=p]"},
            ),
            patch(
                "src.cli.repair.propose.propose_dom_patch",
                _AsyncMock(return_value=None),
            ),
        ):
            return await repair_detail_dom(page, adapter, item_id="7")

    result = asyncio.run(_run())

    assert result.ok is False
    assert result.error == "crawler.dom_repair_failed"


def test_repair_detail_dom_relocates_via_fingerprint_and_persists(tmp_path: Path) -> None:
    extract = tmp_path / "extract.json"
    extract.write_text(
        json.dumps(
            {
                "detail_dom": {
                    "title": "#stale-title",
                    "price": "#stale-price",
                    "want_re": "regex-keep-me",
                }
            }
        ),
        encoding="utf-8",
    )
    tree = {
        "url": "https://www.goofish.com/item?id=7",
        "preview": "商品页面正文",
        "trees": [
            {
                "root": "body",
                "node": {
                    "tag": "div",
                    "classes": ["item-main-info"],
                    "text": "",
                    "kids": [
                        {"tag": "span", "classes": ["price--x"], "text": "¥12", "kids": []},
                    ],
                },
            }
        ],
    }
    page = SimpleNamespace(
        url="https://www.goofish.com/item?id=7",
        evaluate=AsyncMock(side_effect=[tree]),
    )
    adapter = _FakeAdapter(extract)

    async def _run() -> RepairResult:
        with patch("src.crawler.extraction.fingerprint._STORE", tmp_path / "fp.json"):
            fp.save_fingerprint(
                "xianyu",
                "detail_dom",
                "price",
                {"tag": "span", "classes": ["price--x"], "text": "¥12"},
            )
            return await repair_detail_dom(page, adapter, item_id="7")

    result = asyncio.run(_run())

    assert result.ok is True
    assert result.payload and result.payload.get("price") == "¥12"
    assert result.patch and result.patch.source == "fingerprint"
    written = json.loads(extract.read_text(encoding="utf-8"))
    assert "price" in written["detail_dom"]["price"]
    assert 'class*=' in written["detail_dom"]["price"]
    # 其余 section 字段保留
    assert written["detail_dom"]["want_re"] == "regex-keep-me"
