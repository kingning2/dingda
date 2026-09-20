"""节流闸门单测：间隔、并发排号、关闭开关、详情入口接线。"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import patch

import pytest

from crawler.core.pacing import pace
from crawler.core.types import CrawlContext, CrawlItem
from crawler.sources.xianyu import crawler as xianyu_crawler
from crawler.sources.xianyu.crawler import XianyuCrawler, detail_min_interval_s

_INTERVAL = 0.15
_CALLS = 4


def _assert_paced(marks: list[float]) -> None:
    """n 次调用至少横跨 (n-1) 个间隔。

    不断言逐段 gap：``asyncio.sleep`` 只会醒晚不会醒早，一次晚醒会把相邻两段压窄
    （总跨度不变）。跨度才是闸门真正保证的东西。
    """
    assert marks == sorted(marks)
    span = marks[-1] - marks[0]
    expected = _INTERVAL * (_CALLS - 1)
    assert span >= expected * 0.9, (span, expected)


def test_pace_spaces_sequential_calls() -> None:
    async def _run() -> list[float]:
        marks: list[float] = []
        for _ in range(_CALLS):
            await pace("t:sequential", min_interval=_INTERVAL)
            marks.append(time.monotonic())
        return marks

    _assert_paced(asyncio.run(_run()))


def test_pace_serializes_concurrent_callers() -> None:
    """并发调用各自领号 —— 不是一起读到旧时间戳然后全放行。"""

    async def _run() -> list[float]:
        async def one() -> float:
            await pace("t:concurrent", min_interval=_INTERVAL)
            return time.monotonic()

        return sorted(await asyncio.gather(*(one() for _ in range(_CALLS))))

    _assert_paced(asyncio.run(_run()))


def test_pace_disabled_leaves_no_wait() -> None:
    async def _run() -> float:
        started = time.monotonic()
        for _ in range(5):
            await pace("t:off", min_interval=0)
        return time.monotonic() - started

    assert asyncio.run(_run()) < _INTERVAL


def test_detail_min_interval_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DINGDA_DETAIL_MIN_INTERVAL_S", raising=False)
    assert detail_min_interval_s() == 2.5

    monkeypatch.setenv("DINGDA_DETAIL_MIN_INTERVAL_S", "3.5")
    assert detail_min_interval_s() == 3.5

    monkeypatch.setenv("DINGDA_DETAIL_MIN_INTERVAL_S", "0")
    assert detail_min_interval_s() == 0

    monkeypatch.setenv("DINGDA_DETAIL_MIN_INTERVAL_S", "-1")
    assert detail_min_interval_s() == 0

    monkeypatch.setenv("DINGDA_DETAIL_MIN_INTERVAL_S", "not-a-number")
    assert detail_min_interval_s() == 2.5


def test_detail_entry_is_paced(monkeypatch: pytest.MonkeyPatch) -> None:
    """``XianyuCrawler.detail`` 真的过闸 —— 连调 4 次要横跨 3 个间隔。

    绕开真实 mtop：只验证详情入口接了闸门，不验证抓取本身。
    观测点套在 ``pace`` 返回处而不是 ``detail`` 返回处 —— 后者含抓取耗时，
    会反过来把总跨度压短。
    """
    monkeypatch.setenv("DINGDA_DETAIL_MIN_INTERVAL_S", str(_INTERVAL))
    ctx = CrawlContext(task_id="t-paced", meta={"cookie": "unb=1; _m_h5_tk=x_1"})
    crawler = XianyuCrawler(browser=None)  # type: ignore[arg-type]
    item = CrawlItem(item_id="1", title="t", url="u", price=None, raw={})

    released: list[float] = []
    seen: list[tuple[str, float]] = []

    async def _recording_pace(key: str, *, min_interval: float) -> None:
        await pace(key, min_interval=min_interval)
        seen.append((key, min_interval))
        released.append(time.monotonic())

    async def _run() -> None:
        for _ in range(_CALLS):
            result = await crawler.detail(ctx, "1")
            assert result.items[0].title == "t"

    def _keep(item_: Any, session: Any) -> Any:
        return item_

    with (
        patch.object(xianyu_crawler, "pace", _recording_pace),
        patch.object(xianyu_crawler, "mtop_call", return_value={}),
        patch.object(xianyu_crawler, "item_from_mtop_detail", return_value=item),
        patch.object(xianyu_crawler, "_with_comments", side_effect=_keep),
    ):
        asyncio.run(_run())

    assert seen == [("xianyu:detail", _INTERVAL)] * _CALLS
    _assert_paced(released)
