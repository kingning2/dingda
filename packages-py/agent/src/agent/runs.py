"""运行生命周期与投递日志：把 run 从 HTTP 请求里剥出来。

职责：
    ``RunManager`` 持有一批 ``RunRecord``。每个 record 独占一个 ``EventBus`` 的消费端
    （``async for event in bus``），给事件编 ``seq``、记进有界日志、再扇出给订阅者。
    HTTP 生成器只是订阅者之一 —— 它断开只退订，**不杀 run**。于是「关掉应用 /
    刷新 / 断网之后任务还在跑，重进页面能接回来」才成立。

设计说明：
    - ``EventBus`` 语义一个字节不改：``RunManager`` 当它唯一的消费者，于是
      ``context`` / ``loop`` / ``tools`` 里所有 emit 点都不用动。
    - ``start`` 收的是协程工厂 ``factory(bus, cancel) -> int``，cookie / auth / llm
      由 API 层闭包注入 —— 本模块不认识业务，只认识 asyncio。
    - 日志只管**当前 run**（不跨 run 累积），两档淘汰：``browserFrame`` 按 step 只留
      最新一帧（前端本来也只画最后一帧），另有字节上限兜底。淘汰会在 seq 上留洞，
      而重放是「``seq > after`` 的幸存条目」，所以洞是安全的。
    - 重放读的是**日志**，订阅者队列只当唤醒用（事件不从这里取）。少一路缓冲，
      也不需要在「先订阅还是先取快照」之间做取舍。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, NamedTuple

from agent.loop import EXIT_CANCELLED, EXIT_FAILED
from agent.sse import EventBus

logger = logging.getLogger("dingda.agent.runs")

RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"

_CRASH_MESSAGE = "运行出现意外错误，请重试"

# 日志字节上限（估算，见 ``_event_size``）。兜底用：一次长跑的纯文本也不该到几 MB，
# 超了就从最旧的开始淘汰并抬高 ``dropped_through``。
_LOG_BYTES_CAP = 4 * 1024 * 1024

# run 结束后留一段 TTL 供客户端补齐（重进页面接回），之后 ``reap`` 回收。
_FINISHED_TTL_SEC = 15 * 60


RunFactory = Callable[[EventBus, asyncio.Event], Awaitable[int]]
"""一次运行的协程工厂：``(bus, cancel) -> exit_code``。"""


class LogEntry(NamedTuple):
    """日志里的一条：``seq`` 从 1 起、run 内单调，``size`` 是字节估算。"""

    seq: int
    event: dict[str, Any]
    size: int


def _event_size(event: dict[str, Any]) -> int:
    """事件的字节估算（UTF-8）。只用来兜底上限，不必精确到字节。"""
    try:
        return len(json.dumps(event, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return len(str(event))


def _frame_key(event: dict[str, Any]) -> str | None:
    """截图的淘汰键：同键只留最新一帧，非帧返回 None。

    点名了 ``stepId`` 就按它分（扫码登录必须点名，否则二维码会被还在跑的搜索块抢走）；
    没点名就是「当前进行中的 browser_crawl」—— 与前端 reducer 的回退语义一致，
    归到一个槽里，代价是连续两个抓取步骤只留最后一帧。
    """
    if event.get("type") != "browserFrame":
        return None
    step_id = str(event.get("stepId") or "").strip()
    return f"frame:{step_id}" if step_id else "frame:-live-"


class RunRecord:
    """一次运行的全部状态：生命周期、投递日志、订阅者、取消开关。"""

    def __init__(
        self,
        *,
        run_id: str,
        runtime_id: str,
        work_id: str | None = None,
        log_bytes_cap: int = _LOG_BYTES_CAP,
    ) -> None:
        self.run_id = run_id
        self.runtime_id = runtime_id
        self.work_id = work_id
        self.status = RUNNING
        self.seq = 0
        self.exit_code: int | None = None
        self.dropped_through = 0
        self.started_at = time.monotonic()
        self.finished_at: float | None = None
        self.bus = EventBus(run_id)
        self.cancel = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self._log: deque[LogEntry] = deque()
        self._bytes = 0
        self._bytes_cap = log_bytes_cap
        self._latest_frame: dict[str, LogEntry] = {}
        self._wakers: list[asyncio.Queue[None]] = []

    @property
    def subscribers(self) -> int:
        """还在读这条 run 的订阅者数量。"""
        return len(self._wakers)

    @property
    def bytes(self) -> int:
        """日志当前占用的字节估算。"""
        return self._bytes

    def append(self, event: dict[str, Any]) -> LogEntry:
        """编一个 seq、记进日志、唤醒订阅者。"""
        self.seq += 1
        entry = LogEntry(self.seq, event, _event_size(event))
        key = _frame_key(event)
        if key:
            old = self._latest_frame.get(key)
            if old is not None:
                self._drop_entry(old)
            self._latest_frame[key] = entry
        self._log.append(entry)
        self._bytes += entry.size
        self._evict()
        for waker in self._wakers:
            waker.put_nowait(None)
        return entry

    def entries_after(self, after: int) -> list[LogEntry]:
        """``seq > after`` 的幸存条目，按 seq 升序。"""
        return [entry for entry in self._log if entry.seq > after]

    def subscribe(self) -> asyncio.Queue[None]:
        """订阅：拿到一个只用来唤醒的队列（事件从日志读）。"""
        waker: asyncio.Queue[None] = asyncio.Queue()
        self._wakers.append(waker)
        return waker

    def unsubscribe(self, waker: asyncio.Queue[None]) -> None:
        """退订；重复退订不算错。"""
        try:
            self._wakers.remove(waker)
        except ValueError:
            pass

    def finish(self, exit_code: int) -> None:
        """收尾：定状态、唤醒所有订阅者让他们读到终态。幂等。"""
        if self.status != RUNNING:
            return
        self.status = FINISHED if exit_code == 0 else FAILED
        self.exit_code = exit_code
        self.finished_at = time.monotonic()
        for waker in self._wakers:
            waker.put_nowait(None)

    def _drop_entry(self, entry: LogEntry) -> None:
        """从日志里抽掉一条（可能已被字节上限淘汰过，那就什么都不做）。"""
        try:
            self._log.remove(entry)
        except ValueError:
            return
        self._bytes -= entry.size

    def _evict(self) -> None:
        """超上限就从最旧的开始丢，并抬高 ``dropped_through`` 水位。

        至少留一条（``len > 1``）：只留下最新那条才不至于把刚到的帧自己丢掉 ——
        代价是「不超过 上限 + 最大单条」，这个上限是兜底而不是硬承诺。
        """
        while self._bytes > self._bytes_cap and len(self._log) > 1:
            popped = self._log.popleft()
            self._bytes -= popped.size
            self.dropped_through = max(self.dropped_through, popped.seq)


class RunManager:
    """按 run_id 管住一批运行。"""

    def __init__(
        self,
        *,
        log_bytes_cap: int = _LOG_BYTES_CAP,
        finished_ttl: float = _FINISHED_TTL_SEC,
    ) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._bytes_cap = log_bytes_cap
        self._ttl = finished_ttl

    def get(self, run_id: str) -> RunRecord | None:
        """取在册的 run（含已结束但还在 TTL 内的）。"""
        return self._runs.get(run_id)

    def start(
        self,
        *,
        run_id: str,
        runtime_id: str,
        factory: RunFactory,
        work_id: str | None = None,
        seed_events: tuple[dict[str, Any], ...] = (),
    ) -> RunRecord:
        """起手一次运行；同 id 已在跑就接回它（幂等，不重启）。

        ``seed_events`` 是「还没人订阅就该进日志」的事件（``runStarted``）——
        接回时才不会缺了开头那一帧。
        """
        existing = self._runs.get(run_id)
        if existing is not None and existing.status == RUNNING:
            logger.info("run 已在跑，接回而不是重启 run=%s", run_id)
            return existing
        self.reap()

        record = RunRecord(
            run_id=run_id,
            runtime_id=runtime_id,
            work_id=work_id,
            log_bytes_cap=self._bytes_cap,
        )
        self._runs[run_id] = record
        for event in seed_events:
            record.append(event)
        record.task = asyncio.create_task(self._drive(record, factory))
        logger.info("run 起手 run=%s work=%s runtime=%s", run_id, work_id, runtime_id)
        return record

    async def attach(self, run_id: str, after: int = 0) -> AsyncIterator[tuple[int, dict[str, Any]]]:
        """重放 ``seq > after`` 的幸存条目，再续上直播直到 run 结束。

        未知 run 直接结束（端点先查 ``get`` 再 404，这里是防「查到之后被回收」那一线）。
        """
        record = self._runs.get(run_id)
        if record is None:
            return
        waker = record.subscribe()
        last_seq = max(after, record.dropped_through)
        try:
            while True:
                for entry in record.entries_after(last_seq):
                    last_seq = entry.seq
                    yield entry.seq, entry.event
                if record.status != RUNNING:
                    return
                # 队列只为唤醒：醒来回到顶部，事件仍从日志读。append 先入队再让人等，
                # 所以「扫完日志、还没 await」之间到达的事件不会漏。
                await waker.get()
        finally:
            record.unsubscribe(waker)

    def cancel(self, run_id: str) -> bool:
        """给在跑的 run 发取消信号。没有对应运行返回 False。"""
        record = self._runs.get(run_id)
        if record is None or record.status != RUNNING:
            logger.info("取消请求没有对应的在跑运行 run=%s", run_id)
            return False
        record.cancel.set()
        return True

    def active_for_work(self, work_id: str) -> RunRecord | None:
        """这个工作下正在跑的 run（同 id 只会有一条，多轮之间是先后关系）。"""
        key = (work_id or "").strip()
        if not key:
            return None
        candidates = [
            record
            for record in self._runs.values()
            if record.work_id == key and record.status == RUNNING
        ]
        return max(candidates, key=lambda record: record.started_at, default=None)

    def reap(self) -> list[str]:
        """回收已结束、过了 TTL、且没人在读的 run。返回被回收的 id。"""
        now = time.monotonic()
        gone: list[str] = []
        for run_id, record in list(self._runs.items()):
            if record.status == RUNNING or record.subscribers > 0:
                continue
            if record.finished_at is None or now - record.finished_at < self._ttl:
                continue
            del self._runs[run_id]
            gone.append(run_id)
        if gone:
            logger.info("清理过期 run count=%s ids=%s", len(gone), gone)
        return gone

    def reset(self) -> None:
        """清空所有 run（进程收尾与测试用）。

        在跑的任务交给事件循环自己取消（``asyncio.run`` 退出时就会做）—— 跨循环
        按死任务会炸在已关闭的循环上。这里只唤醒还在读的订阅者、清空登记表。
        """
        for record in list(self._runs.values()):
            record.finish(EXIT_CANCELLED)
        self._runs.clear()

    async def _drive(self, record: RunRecord, factory: RunFactory) -> None:
        """跑完一次运行：把 EventBus 抽干进日志，最后补一条 ``runCompleted``。"""
        pump = asyncio.create_task(self._pump(record))
        exit_code = EXIT_FAILED
        try:
            exit_code = await factory(record.bus, record.cancel)
        except asyncio.CancelledError:
            # 收尾（reset / 进程退出）时任务被取消：不再 await 任何东西，标完就走。
            pump.cancel()
            record.finish(EXIT_CANCELLED)
            logger.info("运行被取消 run=%s", record.run_id)
            return
        except Exception:
            # 工厂本该自己吃掉异常；漏到这里也要收尾，不能让前端一直转圈。
            logger.exception("运行内部未预期异常 run=%s", record.run_id)
            await record.bus.put({"type": "error", "message": _CRASH_MESSAGE})
        finally:
            await record.bus.close()

        # 哨兵排在所有事件之后，所以抽干 pump 就等于「事件全进日志了」。
        await pump
        record.append(
            {"type": "runCompleted", "runId": record.run_id, "exitCode": exit_code}
        )
        record.finish(exit_code)
        logger.info("运行收尾 run=%s exit=%s seq=%s", record.run_id, exit_code, record.seq)

    async def _pump(self, record: RunRecord) -> None:
        """把 EventBus 的事件抽进日志（本文件的唯一消费者）。"""
        async for event in record.bus:
            record.append(event)
