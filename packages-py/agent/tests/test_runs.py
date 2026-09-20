"""运行生命周期与投递日志单测（``agent.runs``）。

这里测的是「run 活得比 HTTP 请求长」这件事本身：

- 订阅者走掉**不**杀 run —— 断线重连的地基，最容易在重构里被写回去
- 重放按 ``seq`` 取，洞是安全的（旧帧会被淘汰）
- 保留策略：同 step 只留最新一帧、字节超限抬高 ``dropped_through``
- 收尾保证：正常 / 取消 / 工厂炸了，三条路都要留下 ``runCompleted``
- 未收尾的 run 不回收；还有人读的 run 也不回收

本仓无 pytest-asyncio，测试统一写成 sync + ``asyncio.run``（同 test_run.py）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from agent.loop import EXIT_FAILED, EXIT_OK
from agent.runs import FAILED, FINISHED, RUNNING, RunManager, RunRecord
from agent.sse import EventBus

FRAME = {"type": "browserFrame", "stepId": "s1", "screenshot_url": "data:image/jpeg;base64,AA"}


def _scripted(
    events: Iterable[dict[str, Any]] = (),
    *,
    exit_code: int = EXIT_OK,
    gate: asyncio.Event | None = None,
):
    """推几条事件就返回的工厂；给了 ``gate`` 就先等它放行。"""

    async def factory(bus: EventBus, cancel: asyncio.Event) -> int:
        for event in events:
            await bus.put(event)
        if gate is not None:
            await gate.wait()
        return exit_code

    return factory


def _kinds(record: RunRecord, after: int = 0) -> list[str]:
    """日志里 ``seq > after`` 的事件类型，按顺序。"""
    return [str(entry.event["type"]) for entry in record.entries_after(after)]


def test_subscriber_leaving_does_not_kill_the_run() -> None:
    """断开只退订：任务照跑、日志照记 —— 这是断线重连成立的前提。"""

    async def scenario() -> tuple[bool, list[str], int, int, int | None, list[str]]:
        manager = RunManager()
        gate = asyncio.Event()
        record = manager.start(
            run_id="r1",
            runtime_id="dingda",
            work_id="w1",
            factory=_scripted([{"type": "textDelta", "text": "一"}], gate=gate),
            seed_events=({"type": "runStarted"},),
        )

        consumed: list[str] = []
        stream = manager.attach("r1")
        async for _seq, event in stream:
            consumed.append(str(event["type"]))
            if len(consumed) >= 2:
                break
        await stream.aclose()

        alive = record.status == RUNNING and not record.task.done()
        subscribers = record.subscribers
        gate.set()
        await record.task
        return alive, consumed, subscribers, record.status, record.exit_code, _kinds(record)

    alive, consumed, subscribers, status, exit_code, kinds = asyncio.run(scenario())

    assert consumed == ["runStarted", "textDelta"]
    assert alive, "订阅者走掉不该结束 run"
    assert subscribers == 0, "生成器关掉就该退订"
    assert status == FINISHED
    assert exit_code == EXIT_OK
    # 断开期间没人读，事件照样全在日志里 —— 接回时能补齐
    assert kinds == ["runStarted", "textDelta", "runCompleted"]


def test_replay_returns_only_newer_seq() -> None:
    """``after=N`` 只给 ``seq > N`` 且严格递增：断点续传靠它不重不漏。"""

    async def scenario() -> list[int]:
        manager = RunManager()
        record = manager.start(
            run_id="r1",
            runtime_id="dingda",
            factory=_scripted([{"type": "textDelta", "text": str(i)} for i in range(4)]),
            seed_events=({"type": "runStarted"},),
        )
        await record.task
        return [seq async for seq, _ in manager.attach("r1", after=2)]

    assert asyncio.run(scenario()) == [3, 4, 5, 6]


def test_frames_are_compacted_per_step() -> None:
    """同一个 step 只留最新一帧：旧的 seq 成为洞，重放时自然跳过。"""

    async def scenario() -> list[tuple[int, str]]:
        manager = RunManager()
        record = manager.start(
            run_id="r1",
            runtime_id="dingda",
            factory=_scripted([dict(FRAME, screenshot_url=f"data:{i}") for i in range(3)]),
        )
        await record.task
        return [
            (entry.seq, str(entry.event.get("screenshot_url") or entry.event["type"]))
            for entry in record.entries_after(0)
        ]

    # 三帧压成一帧（seq 3），收尾在 seq 4
    assert asyncio.run(scenario()) == [(3, "data:2"), (4, "runCompleted")]


def test_named_steps_keep_their_own_latest_frame() -> None:
    """点名了 stepId 的帧各留各的：扫码二维码不会被还在跑的搜索帧顶掉。"""

    async def scenario() -> list[tuple[int, str]]:
        manager = RunManager()
        record = manager.start(
            run_id="r1",
            runtime_id="dingda",
            factory=_scripted(
                [
                    dict(FRAME, stepId="login", screenshot_url="data:qr-1"),
                    dict(FRAME, stepId="search", screenshot_url="data:list"),
                    dict(FRAME, stepId="login", screenshot_url="data:qr-2"),
                ]
            ),
        )
        await record.task
        return [
            (entry.seq, str(entry.event.get("screenshot_url")))
            for entry in record.entries_after(0)
            if entry.event["type"] == "browserFrame"
        ]

    assert asyncio.run(scenario()) == [(2, "data:list"), (3, "data:qr-2")]


def test_byte_cap_drops_oldest_and_raises_watermark() -> None:
    """字节超限从最旧丢起并抬高 ``dropped_through``；重放不假装那些事件还在。"""

    async def scenario() -> tuple[int, list[int], list[str], str]:
        manager = RunManager(log_bytes_cap=700)
        record = manager.start(
            run_id="r1",
            runtime_id="dingda",
            factory=_scripted([{"type": "textDelta", "text": "x" * 200} for _ in range(4)]),
        )
        await record.task
        replayed = [seq async for seq, _ in manager.attach("r1", after=0)]
        last_text = next(
            str(entry.event.get("text"))
            for entry in reversed(record.entries_after(0))
            if entry.event["type"] == "textDelta"
        )
        return record.dropped_through, replayed, _kinds(record), last_text

    dropped_through, replayed, kinds, last_text = asyncio.run(scenario())

    assert dropped_through > 0, "这么大的正文早该触发淘汰"
    assert replayed == sorted(replayed)
    assert replayed[0] == dropped_through + 1, "重放从水位之后开始，不谎报丢掉的那几条"
    assert last_text == "x" * 200, "最新那条正文必须留着"
    assert kinds[-1] == "runCompleted", "收尾那条永远留得住，客户端才能落地"


def test_cancel_only_signals_a_running_run() -> None:
    """取消只对在跑的那条为真；已结束与不存在的都返回 False。"""

    async def scenario() -> tuple[bool, bool, bool, bool]:
        manager = RunManager()
        gate = asyncio.Event()
        record = manager.start(run_id="r1", runtime_id="dingda", factory=_scripted(gate=gate))
        signalled = manager.cancel("r1")
        seen = record.cancel.is_set()
        gate.set()
        await record.task
        return signalled, seen, manager.cancel("r1"), manager.cancel("nope")

    assert asyncio.run(scenario()) == (True, True, False, False)


def test_start_returns_the_running_run_instead_of_restarting() -> None:
    """同一个 run_id 再起一次是接回：不重启、不重记 ``runStarted``。"""

    async def scenario() -> tuple[bool, str, list[str]]:
        manager = RunManager()
        gate = asyncio.Event()
        first = manager.start(
            run_id="r1",
            runtime_id="dingda",
            factory=_scripted([{"type": "textDelta", "text": "一"}], gate=gate),
            seed_events=({"type": "runStarted"},),
        )
        second = manager.start(run_id="r1", runtime_id="其它", factory=_scripted())
        gate.set()
        await first.task
        return first is second, second.runtime_id, _kinds(first)

    assert asyncio.run(scenario()) == (True, "dingda", ["runStarted", "textDelta", "runCompleted"])


def test_unknown_run_replays_nothing() -> None:
    """接回一个不在册的 run 得到空流，而不是异常。"""

    async def scenario() -> list[Any]:
        manager = RunManager()
        return [pair async for pair in manager.attach("没这条")]

    assert asyncio.run(scenario()) == []


def test_active_run_lookup_is_by_work() -> None:
    """活跃探针按 work 找在跑的 run；跑完或 work 不匹配都没有。"""

    async def scenario() -> list[Any]:
        manager = RunManager()
        gate = asyncio.Event()
        record = manager.start(
            run_id="r1", runtime_id="dingda", work_id="w1", factory=_scripted(gate=gate)
        )
        found = manager.active_for_work("w1")
        missing = manager.active_for_work("w2")
        blank = manager.active_for_work("  ")
        gate.set()
        await record.task
        return [found is record, missing, blank, manager.active_for_work("w1")]

    assert asyncio.run(scenario()) == [True, None, None, None]


def test_reap_keeps_subscribed_runs() -> None:
    """TTL 到了也要等读者走完；还在读的 run 不回收。"""

    async def scenario() -> tuple[list[str], int, list[str]]:
        manager = RunManager(finished_ttl=0.0)
        record = manager.start(run_id="done", runtime_id="dingda", factory=_scripted())
        await record.task

        stream = manager.attach("done")
        await stream.__anext__()
        kept = manager.reap()
        while_subscribed = record.subscribers
        await stream.aclose()
        return kept, while_subscribed, manager.reap()

    kept, while_subscribed, after = asyncio.run(scenario())

    assert (kept, while_subscribed) == ([], 1)
    assert after == ["done"]


def test_factory_crash_still_completes(caplog: Any) -> None:
    """工厂炸了也要留下 ``runCompleted`` —— 前端靠它把消息从「运行中」放下来。"""
    caplog.set_level(logging.CRITICAL, logger="dingda.agent.runs")

    async def scenario() -> tuple[list[str], int, int | None]:
        manager = RunManager()

        async def boom(bus: EventBus, cancel: asyncio.Event) -> int:
            await bus.put({"type": "textDelta", "text": "半截"})
            raise RuntimeError("炸了")

        record = manager.start(run_id="r1", runtime_id="dingda", factory=boom)
        await record.task
        return _kinds(record), record.status, record.exit_code

    kinds, status, exit_code = asyncio.run(scenario())

    assert kinds == ["textDelta", "error", "runCompleted"]
    assert status == FAILED
    assert exit_code == EXIT_FAILED


def test_encode_carries_seq_as_sse_id() -> None:
    """``id:`` 行是重放游标；不给 seq 时帧格式与从前逐字一致。"""
    bus = EventBus("r1")

    with_id = bus.encode({"type": "textDelta", "text": "一"}, seq=7)
    assert with_id.startswith("id: 7\nevent: textDelta\n")

    without = bus.encode({"type": "textDelta", "text": "一"})
    assert without.startswith("event: textDelta\n")
    assert "id:" not in without
