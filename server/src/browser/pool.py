"""单机 BrowserPool：多 Camoufox 进程的创建、复用、排队与回收。

职责：
    在 max_browsers / max_contexts_per_browser 限制下分配 BrowserInstance。
    有空闲则复用，未满则新建，满则等待；空闲超时回收；启动失败与异常退出后按需再拉起。

设计说明：
    - 单机内存调度，不引入 Redis / K8s
    - Crawler 只拿 PooledPort，禁止直接 launch/close 引擎
    - 进程级 Browser Runtime 仍是 Python Server；不另起一套 Runtime

使用示例：
    port = await pool.acquire()
    try:
        page = await port.open(...)
    finally:
        await page.close()
        await pool.release(port)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import ClassVar, Mapping, Sequence

from src.browser.instance import BrowserInstance, BrowserState
from src.browser.port import BrowserPort, Cookie, LaunchOptions, Page
from src.browser.registry import create_browser

logger = logging.getLogger("dingda.browser.pool")

_DEFAULT_IDLE_SECONDS = 600
_DEFAULT_MAX_BROWSERS = 3
_DEFAULT_MAX_CONTEXTS = 5
_DEAD_MARKERS = (
    "has been closed",
    "target closed",
    "browser closed",
    "connection closed",
    "browser has been disconnected",
)


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, float(raw))
    except ValueError:
        return default


def _env_int(name: str, default: int, *, minimum: int) -> int:
    return int(_env_float(name, float(default), minimum=float(minimum)))


def pool_idle_timeout_s() -> float:
    """空闲回收秒数，默认 10 分钟。"""
    return _env_float("DINGDA_BROWSER_IDLE_SECONDS", float(_DEFAULT_IDLE_SECONDS), minimum=1.0)


def pool_max_browsers() -> int:
    """同时存活的 Browser 进程上限。"""
    return _env_int("DINGDA_BROWSER_MAX", _DEFAULT_MAX_BROWSERS, minimum=1)


def pool_max_contexts() -> int:
    """每台 Browser 同时占用的 Context/任务上限。"""
    return _env_int("DINGDA_BROWSER_MAX_CONTEXTS", _DEFAULT_MAX_CONTEXTS, minimum=1)


def _looks_dead(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _DEAD_MARKERS)


class PooledPort(BrowserPort):
    """任务租约：把某台 BrowserInstance 暴露成 BrowserPort。"""

    engine: ClassVar[str] = "camoufox"

    def __init__(self, pool: BrowserPool, instance: BrowserInstance) -> None:
        self._pool = pool
        self._instance = instance
        self.browser_id = instance.browser_id
        self.engine = instance.engine

    async def launch(self, options: LaunchOptions | None = None) -> None:
        """池内已启动；忽略调用方 launch。"""
        return None

    async def open(
        self,
        *,
        proxy: str | None = None,
        fingerprint: str | None = None,
        cookies: Sequence[Cookie] | Mapping[str, str] | None = None,
        default_domain: str = "",
    ) -> Page:
        """在租约对应的 Browser 上开 Context/Page。"""
        port = self._instance.port
        if port is None:
            raise RuntimeError(f"浏览器 {self.browser_id} 已停止")
        try:
            return await port.open(
                proxy=proxy,
                fingerprint=fingerprint,
                cookies=cookies,
                default_domain=default_domain,
            )
        except Exception as exc:
            if _looks_dead(exc):
                logger.warning(
                    "浏览器已异常退出 browser_id=%s 原因=开页失败 err=%s",
                    self.browser_id,
                    exc,
                )
                await self._pool.retire(self._instance, reason="开页失败")
            raise

    async def close(self) -> None:
        """任务不得关 Browser 进程；请 release 租约。"""
        logger.info("忽略对池内浏览器的 close，请走 release browser_id=%s", self.browser_id)


class BrowserPool:
    """进程内单机 Browser 池。"""

    def __init__(
        self,
        engine: str = "camoufox",
        *,
        max_browsers: int | None = None,
        max_contexts_per_browser: int | None = None,
        idle_timeout_s: float | None = None,
    ) -> None:
        self._engine = engine
        self._max_browsers = max_browsers if max_browsers is not None else pool_max_browsers()
        self._max_contexts = (
            max_contexts_per_browser
            if max_contexts_per_browser is not None
            else pool_max_contexts()
        )
        self._idle_timeout_s = (
            idle_timeout_s if idle_timeout_s is not None else pool_idle_timeout_s()
        )
        self._instances: list[BrowserInstance] = []
        self._lock = asyncio.Lock()
        self._cv = asyncio.Condition(self._lock)
        self._stopped = False

    @property
    def engine(self) -> str:
        return self._engine

    @property
    def max_browsers(self) -> int:
        return self._max_browsers

    @property
    def max_contexts_per_browser(self) -> int:
        return self._max_contexts

    @property
    def idle_timeout_s(self) -> float:
        return self._idle_timeout_s

    def peek(self) -> BrowserInstance | None:
        """已就绪的第一台（测试/start 后取 Port）。"""
        for inst in self._instances:
            if inst.port is not None and inst.state not in {
                BrowserState.STARTING,
                BrowserState.CLOSING,
                BrowserState.STOPPED,
            }:
                return inst
        return None

    async def acquire(self, options: LaunchOptions | None = None) -> PooledPort:
        """申请一个 Context 槽位；必要时启动新 Browser 或排队。"""
        failures = 0
        while True:
            if self._stopped:
                raise RuntimeError("浏览器池已关闭")
            launch_inst: BrowserInstance | None = None
            async with self._cv:
                if self._stopped:
                    raise RuntimeError("浏览器池已关闭")
                inst = self._pick_locked()
                if inst is not None:
                    self._occupy_locked(inst)
                    logger.info(
                        "复用已有浏览器 browser_id=%s occupancy=%s state=%s alive=%s",
                        inst.browser_id,
                        inst.occupancy,
                        inst.state,
                        self._slot_count_locked(),
                    )
                    return PooledPort(self, inst)
                if self._slot_count_locked() < self._max_browsers:
                    launch_inst = self._reserve_locked(options)
                else:
                    logger.info(
                        "浏览器池已满，排队等待 max_browsers=%s max_contexts=%s alive=%s",
                        self._max_browsers,
                        self._max_contexts,
                        self._slot_count_locked(),
                    )
                    await self._cv.wait()
                    continue
            assert launch_inst is not None
            try:
                await launch_inst.launch(create_browser)
            except Exception:
                failures += 1
                logger.exception(
                    "浏览器启动失败 browser_id=%s 第%s次",
                    launch_inst.browser_id,
                    failures,
                )
                async with self._cv:
                    await self._drop_locked(launch_inst, reason="启动失败")
                    self._cv.notify_all()
                if failures >= 3:
                    raise
                continue
            async with self._cv:
                if self._stopped:
                    await self._drop_locked(launch_inst, reason="主动关闭")
                    raise RuntimeError("浏览器池已关闭")
                if launch_inst.state == BrowserState.STOPPED:
                    continue
                launch_inst.sync_state(self._max_contexts)
                self._occupy_locked(launch_inst)
                self._cv.notify_all()
                logger.info(
                    "新浏览器已接入任务 browser_id=%s occupancy=%s alive=%s",
                    launch_inst.browser_id,
                    launch_inst.occupancy,
                    self._slot_count_locked(),
                )
                return PooledPort(self, launch_inst)

    async def release(self, port: BrowserPort) -> None:
        """归还 Context 槽位；该 Browser 无人使用则开始空闲计时。"""
        browser_id = getattr(port, "browser_id", None)
        async with self._cv:
            inst = self._find_locked(browser_id)
            if inst is None:
                logger.info("归还槽位时未找到实例 browser_id=%s", browser_id)
                return
            if inst.occupancy > 0:
                inst.occupancy -= 1
            inst.sync_state(self._max_contexts)
            logger.info(
                "归还浏览器槽位 browser_id=%s occupancy=%s state=%s",
                inst.browser_id,
                inst.occupancy,
                inst.state,
            )
            if inst.occupancy == 0 and not inst.pinned and inst.port is not None:
                inst.idle_since = time.monotonic()
                self._schedule_idle_locked(inst)
            self._cv.notify_all()

    async def ensure_pinned(self, options: LaunchOptions | None = None) -> PooledPort:
        """独占预热一台 Browser，直到 stop；供风控恢复 start() 使用。"""
        async with self._cv:
            if self._stopped:
                raise RuntimeError("浏览器池已关闭")
            ready = self.peek()
            if ready is not None:
                ready.pinned = True
                ready.cancel_idle()
                ready.sync_state(self._max_contexts)
                logger.info("钉住已有浏览器 browser_id=%s", ready.browser_id)
                return PooledPort(self, ready)
            inst = self._reserve_locked(options)
        try:
            await inst.launch(create_browser)
        except Exception:
            async with self._cv:
                await self._drop_locked(inst, reason="启动失败")
                self._cv.notify_all()
            raise
        async with self._cv:
            if self._stopped:
                await self._drop_locked(inst, reason="主动关闭")
                raise RuntimeError("浏览器池已关闭")
            inst.pinned = True
            inst.sync_state(self._max_contexts)
            logger.info("钉住新浏览器 browser_id=%s state=%s", inst.browser_id, inst.state)
            return PooledPort(self, inst)

    async def retire(self, instance: BrowserInstance, *, reason: str) -> None:
        """异常退出：关掉该实例，有排队任务时由后续 acquire 按需再拉起。"""
        async with self._cv:
            if instance.state == BrowserState.STOPPED:
                return
            logger.warning(
                "浏览器异常退役 browser_id=%s 原因=%s 将按需重启",
                instance.browser_id,
                reason,
            )
            await self._drop_locked(instance, reason=reason)
            self._cv.notify_all()

    async def stop(self) -> None:
        """关闭池内全部 Browser。"""
        async with self._cv:
            self._stopped = True
            instances = list(self._instances)
            self._cv.notify_all()
        for inst in instances:
            async with self._cv:
                if inst.state == BrowserState.STOPPED:
                    continue
                await self._drop_locked(inst, reason="主动关闭")
            # 释放锁后再关下一台，避免长时间占锁
        async with self._cv:
            self._instances.clear()
            logger.info("浏览器池已全部关闭 engine=%s", self._engine)

    def _slot_count_locked(self) -> int:
        return sum(
            1
            for inst in self._instances
            if inst.state != BrowserState.STOPPED
        )

    def _find_locked(self, browser_id: str | None) -> BrowserInstance | None:
        if not browser_id:
            return None
        for inst in self._instances:
            if inst.browser_id == browser_id:
                return inst
        return None

    def _pick_locked(self) -> BrowserInstance | None:
        candidates = [inst for inst in self._instances if inst.can_accept(self._max_contexts)]
        if not candidates:
            return None
        candidates.sort(key=lambda inst: (inst.occupancy, inst.browser_id))
        return candidates[0]

    def _reserve_locked(self, options: LaunchOptions | None) -> BrowserInstance:
        inst = BrowserInstance(self._engine, options)
        self._instances.append(inst)
        logger.info(
            "创建浏览器实例 browser_id=%s engine=%s profile=%s alive=%s max=%s",
            inst.browser_id,
            self._engine,
            inst.profile,
            self._slot_count_locked(),
            self._max_browsers,
        )
        return inst

    def _occupy_locked(self, inst: BrowserInstance) -> None:
        inst.occupancy += 1
        inst.idle_since = None
        inst.cancel_idle()
        inst.sync_state(self._max_contexts)
        logger.info(
            "占用浏览器槽位 browser_id=%s occupancy=%s state=%s",
            inst.browser_id,
            inst.occupancy,
            inst.state,
        )

    def _schedule_idle_locked(self, inst: BrowserInstance) -> None:
        inst.cancel_idle()
        inst.idle_task = asyncio.create_task(
            self._idle_recycle(inst),
            name=f"browser-idle-{inst.browser_id}",
        )
        logger.info(
            "开始空闲倒计时 browser_id=%s timeout=%ss",
            inst.browser_id,
            int(self._idle_timeout_s),
        )

    async def _idle_recycle(self, inst: BrowserInstance) -> None:
        try:
            await asyncio.sleep(self._idle_timeout_s)
        except asyncio.CancelledError:
            return
        async with self._cv:
            if inst.occupancy > 0 or inst.pinned or inst.port is None:
                return
            if inst.state == BrowserState.STOPPED:
                return
            idle_for = time.monotonic() - (inst.idle_since or time.monotonic())
            logger.info(
                "空闲回收浏览器 browser_id=%s idle_for=%.0fs",
                inst.browser_id,
                idle_for,
            )
            await self._drop_locked(inst, reason="空闲回收")
            self._cv.notify_all()

    async def _drop_locked(self, inst: BrowserInstance, *, reason: str) -> None:
        if inst.state == BrowserState.STOPPED:
            if inst in self._instances:
                self._instances.remove(inst)
            return
        await inst.close(reason=reason)
        if inst in self._instances:
            self._instances.remove(inst)
