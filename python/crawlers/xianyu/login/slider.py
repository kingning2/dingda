"""闲鱼滑块自动求解 — 对齐商业版 human 拖动轨迹与反检测。

负责：
- 在主页 / iframe 中定位 `#nc_1_n1z` 滑块与轨道（含启发式兜底）；
- 生成拟人拖动轨迹（三种方案轮换：容器内 / 超出容器 / 最小急动度）；
- 用 CDP 真实鼠标事件（带 deltaX/deltaY）拖动，修复 movementX=0 机器人特征；
- 以 x5sec Cookie 或弹窗消失判定成功，失败时清 risk cookies 重试。

参考 XianYuPilo sliderSolver.ts：三种轨迹方案按尝试轮换，对抗
Baxia FireyeJS 的 ML 轨迹检测；默认优先最小急动度剖面（Hogan 1984）。
Camoufox 路径关闭包内 humanize，由本模块控制拖动节奏，避免逐步 mouse.move
被拉到秒级。

作者：Xiaoman
创建时间：2026-08-20
"""

from __future__ import annotations

import contextlib
import logging
import math
import random
import time
from typing import Any

logger = logging.getLogger("dingda.sidecar.slider-solve")

BUTTON_SELECTORS = (
    "#nc_1_n1z",
    ".nc_iconfont.btn_slide",
    ".btn_slide",
    ".nc_iconfont",
    ".slide-btn",
    "#aliyunCaptcha-sliding-slider",
    ".J_MIDDLEWARE_FRAME .btn_slide",
    "span.nc_iconfont",
    "div[draggable='true'][class*='slide']",
)
TRACK_SELECTORS = (
    "#nc_1_n1t",
    ".nc_scale",
    ".scale_text",
    ".slide-track",
    "#nc_1__scale",
    ".nc-lang-cnt",
    ".slide-verify-track",
    "[class*='track']",
)
RETRY_SELECTORS = (
    "#nc_1_refresh1",
    ".nc_iconfont.btn_refresh",
    "text=刷新",
    "text=重试",
)
SUCCESS_SELECTORS = (".nc_ok", ".success", "#nc_1_n1z.success", ".icon-success")
FAIL_SELECTORS = (".nc_error", ".errloading", ".fail", "#nc_1_refresh1")

# Baxia 风控在访问过程中通过 Set-Cookie 重新设置的 risk cookies，
# 刷新重试前必须清除，否则会形成"刷新→带 risk cookies→再次 punish→刷新"死循环。
RISK_COOKIE_NAMES = (
    "x5secdata",
    "x5sec",
    "x5sectag",
    "x5pref",
    "bx-cookie-test",
    "tfstk",
    "cbc",
    "sca",
    "isg",
)

STRATEGY_NAMES = {0: "最小急动度物理拖动", 1: "容器内拖动", 2: "超出容器拖动"}


def _strategy_for_attempt(attempt: int) -> int:
    """按尝试序号选择轨迹：优先物理拖动（Camoufox 上已验证更快更稳）。

    @param attempt 1-based 尝试次数
    @returns 0=物理 / 1=容器内 / 2=超出容器
    """
    return (attempt - 1) % 3


def has_x5sec(cookies: list[dict[str, Any]]) -> bool:
    """判断 Cookie 列表是否已含 x5 安全凭证。

    @param cookies Cookie 字典列表
    @returns 含 x5 / x5sec 时返回 True
    """
    for cookie in cookies:
        name = str(cookie.get("name") or "").lower()
        if name.startswith("x5") or "x5sec" in name:
            return True
    return False


async def clear_risk_cookies(context: Any) -> None:
    """刷新重试前清除 risk cookies，避免"刷新→带 risk→再 punish"死循环。

    @param context Playwright BrowserContext
    """
    try:
        cookies = await context.cookies()
        clean = [c for c in cookies if c.get("name") not in RISK_COOKIE_NAMES]
        if len(clean) != len(cookies):
            await context.clear_cookies()
            await context.add_cookies(clean)
    except Exception:  # noqa: BLE001
        logger.warning("清除 risk cookies 失败（不影响主流程）")


async def _find_in_scopes(page: Any, selectors: tuple[str, ...]) -> tuple[Any | None, Any | None]:
    """在主页面与全部 frame 中查找首个可见元素。

    @param page Playwright Page
    @param selectors CSS 选择器列表
    @returns (element, scope) — scope 为 page 或 frame；未找到返回 (None, None)
    """
    scopes: list[Any] = [page]
    with contextlib.suppress(Exception):
        scopes.extend(page.frames)

    for scope in scopes:
        for selector in selectors:
            try:
                element = await scope.query_selector(selector)
                if element is None:
                    continue
                try:
                    if not await element.is_visible():
                        continue
                except Exception:  # noqa: BLE001
                    pass
                return element, scope
            except Exception:  # noqa: BLE001
                continue
    return None, None


async def find_slider(page: Any) -> tuple[Any | None, Any | None, Any | None]:
    """查找滑块按钮与轨道。

    @param page Playwright Page
    @returns (button, track, scope)
    """
    button, scope = await _find_in_scopes(page, BUTTON_SELECTORS)
    if button is None or scope is None:
        return None, None, None

    track = None
    for selector in TRACK_SELECTORS:
        try:
            candidate = await scope.query_selector(selector)
            if candidate is None:
                continue
            try:
                if await candidate.is_visible():
                    track = candidate
                    break
            except Exception:  # noqa: BLE001
                track = candidate
                break
        except Exception:  # noqa: BLE001
            continue

    if track is None:
        # 无独立轨道时，用按钮父节点估算宽度
        try:
            track = await button.evaluate_handle("el => el.parentElement")
        except Exception:  # noqa: BLE001
            return button, None, scope
    return button, track, scope


async def _slide_distance(button: Any, track: Any, scope: Any) -> float:
    """计算滑动距离（轨道宽 - 按钮宽），钳制到常见区间。

    @param button 滑块按钮
    @param track 轨道元素
    @param scope page 或 frame（用于 JS 精确计算）
    @returns 像素距离；失败返回 0
    """
    evaluate = getattr(scope, "evaluate", None)
    if evaluate is not None:
        try:
            precise = await evaluate(
                """() => {
                    const button = document.querySelector('#nc_1_n1z')
                        || document.querySelector('.nc_iconfont.btn_slide')
                        || document.querySelector('.btn_slide');
                    const track = document.querySelector('#nc_1_n1t')
                        || document.querySelector('.nc_scale')
                        || document.querySelector('.nc-lang-cnt');
                    if (button && track) {
                        const br = button.getBoundingClientRect();
                        const tr = track.getBoundingClientRect();
                        return tr.width - br.width;
                    }
                    return null;
                }"""
            )
            if isinstance(precise, (int, float)) and precise > 10:
                return float(max(180.0, min(360.0, precise))) + random.uniform(-0.5, 0.5)
        except Exception:  # noqa: BLE001
            pass

    button_box = await button.bounding_box()
    track_box = await track.bounding_box() if track is not None else None
    if not button_box:
        return 0.0
    if track_box:
        width = max(180.0, min(360.0, track_box["width"] - button_box["width"]))
        return width + random.uniform(-0.5, 0.5)
    return 260.0 + random.uniform(0, 20)


class CdpMouse:
    """CDP 鼠标封装：手动设置 deltaX/deltaY，修复 movementX/movementY 恒为 0。

    Playwright 的 page.mouse.move() 经 CDP Input.dispatchMouseEvent 发送时不携带
    deltaX/deltaY，导致 event.movementX/movementY 恒为 0，这是 FireyeJS 识别
    机器人的强信号。此处手动填充增量。
    """

    def __init__(self, client: Any, start_x: float, start_y: float) -> None:
        self._client = client
        self._x = start_x
        self._y = start_y
        self._pressed = False

    async def _dispatch(
        self,
        event_type: str,
        x: float,
        y: float,
        buttons: int,
        *,
        click_count: int = 1,
    ) -> None:
        dx = round((x - self._x) * 100) / 100
        dy = round((y - self._y) * 100) / 100
        self._x = x
        self._y = y
        await self._client.send(
            "Input.dispatchMouseEvent",
            {
                "type": event_type,
                "x": x,
                "y": y,
                "deltaX": dx,
                "deltaY": dy,
                "button": "left",
                "buttons": buttons,
                "modifiers": 0,
                "clickCount": click_count,
                "timestamp": 0,
            },
        )

    async def move(self, x: float, y: float, steps: int = 1) -> None:
        """移动（steps>1 时线性插值，逐点附带正确 deltaX/deltaY）。"""
        for index in range(1, steps + 1):
            t = index / steps
            await self._dispatch(
                "mouseMoved",
                self._x + (x - self._x) * t,
                self._y + (y - self._y) * t,
                1 if self._pressed else 0,
            )

    async def down(self, x: float, y: float) -> None:
        await self._dispatch("mousePressed", x, y, 1)
        self._pressed = True

    async def up(self, x: float, y: float) -> None:
        await self._dispatch("mouseReleased", x, y, 0)
        self._pressed = False


class PageMouseFallback:
    """CDP 不可用时的 page.mouse 回退（无 delta，但保证流程可用）。"""

    def __init__(self, page: Any) -> None:
        self._page = page

    async def move(self, x: float, y: float, steps: int = 1) -> None:
        await self._page.mouse.move(x, y, steps=steps)

    async def down(self, x: float, y: float) -> None:
        await self._page.mouse.down()

    async def up(self, x: float, y: float) -> None:
        await self._page.mouse.up()


async def _create_drag_mouse(
    page: Any,
    start_x: float,
    start_y: float,
    *,
    prefer_page_mouse: bool = False,
) -> CdpMouse | PageMouseFallback:
    """创建拖动鼠标：Chromium 优先 CDP（带 delta）；Camoufox/Firefox 用 page.mouse。"""
    if prefer_page_mouse or _is_firefox_page(page):
        logger.info("滑块使用 page.mouse（Firefox/Camoufox）")
        return PageMouseFallback(page)
    try:
        client = await page.context.new_cdp_session(page)
        return CdpMouse(client, start_x, start_y)
    except Exception:  # noqa: BLE001
        return PageMouseFallback(page)


def _is_firefox_page(page: Any) -> bool:
    """当前页是否为 Firefox / Camoufox（无 CDP Input 路径）。"""
    with contextlib.suppress(Exception):
        browser = page.context.browser
        if browser is not None and getattr(browser, "browser_type", None) is not None:
            name = (browser.browser_type.name or "").lower()
            if name in {"firefox", "camoufox"}:
                return True
    return False


async def _human_like_drag(
    page: Any,
    mouse: CdpMouse | PageMouseFallback,
    start_x: float,
    start_y: float,
    distance: float,
    attempt: int,
) -> None:
    """容器内拟人拖动：不对称三阶段速度 + 中间停顿 + 终点过冲回退。

    总时长压在约 0.8–1.4s（与物理轨迹同量级）。勿对单步使用大 ``steps``：
    Camoufox humanize / Playwright 插值会把每步拖成秒级。
    """
    del attempt  # 保留签名兼容；时长用随机档而非 attempt 放大
    total_ms = random.uniform(800, 1400)
    steps = random.randint(45, 70)
    avg_delay = total_ms / steps
    pauses = 1 if random.random() < 0.5 else 0

    actual_x = start_x + random.uniform(-4, 4)
    actual_y = start_y + random.uniform(-3, 3)
    pause_point = random.uniform(0.3, 0.7)
    arc_dir = -1 if random.random() < 0.5 else 1
    arc_amp = random.uniform(3, 8)
    last_x = actual_x
    last_y = actual_y

    for index in range(1, steps + 1):
        progress = index / steps
        eased = progress**2.5 / (progress**2.5 + (1 - progress) ** 2.5)
        target_x = actual_x + distance * eased
        if random.random() < 0.05 and 3 < index < steps - 3:
            target_x = last_x - random.uniform(2, 5)
        arc_offset = arc_dir * arc_amp * math.sin(math.pi * progress)
        current_y = last_y * 0.6 + (actual_y + arc_offset + random.uniform(-3, 3)) * 0.4
        last_y = current_y
        await mouse.move(target_x, current_y, 1)
        await page.wait_for_timeout(max(1, int(avg_delay + random.uniform(-2.5, 2.5))))
        last_x = target_x
        if pauses and progress >= pause_point:
            pauses -= 1
            pause_point = random.uniform(0.3, 0.7)
            await page.wait_for_timeout(int(random.uniform(80, 160)))

    await page.wait_for_timeout(int(random.uniform(30, 80)))
    overshoot = random.uniform(5, 13)
    await mouse.move(actual_x + distance + overshoot, actual_y + random.uniform(-5, 5), 1)
    await page.wait_for_timeout(int(random.uniform(40, 90)))
    await mouse.move(actual_x + distance, actual_y + random.uniform(-3, 3), 1)
    await page.wait_for_timeout(int(random.uniform(40, 90)))
    await mouse.up(actual_x + distance, last_y)


async def _human_like_drag_out(
    page: Any,
    mouse: CdpMouse | PageMouseFallback,
    start_x: float,
    start_y: float,
    distance: float,
    attempt: int,
) -> None:
    """超出容器范围的拟人拖动：Y 大幅偏移（±50-120px）模拟手部自由移动。

    与容器内拖动互补：真人拖动时鼠标可随意超出弹窗范围，只要已按下且整体
    向右移动，Baxia 仍会判定为有效滑动。总时长约 0.8–1.4s。
    """
    del attempt
    total_ms = random.uniform(800, 1400)
    steps = random.randint(40, 65)
    avg_delay = total_ms / steps

    out_points: list[tuple[float, float]] = []
    count = random.randint(2, 3)
    for index in range(count):
        progress = 0.2 + (0.6 * (index + 1) / (count + 1)) + random.uniform(-0.05, 0.05)
        direction = -1 if index % 2 == 0 else 1
        out_points.append((max(0.15, min(0.85, progress)), direction * random.uniform(50, 120)))

    last_x = start_x
    for index in range(1, steps + 1):
        progress = index / steps
        eased = progress * progress * (3 - 2 * progress)
        target_x = start_x + distance * eased
        if random.random() < 0.05 and 3 < index < steps - 3:
            target_x = last_x - random.uniform(2, 5)
        y_offset = math.sin(math.pi * progress) * 5
        for point_progress, point_offset in out_points:
            dist = abs(progress - point_progress)
            if dist < 0.15:
                influence = math.exp(-(dist * dist) / (2 * 0.05 * 0.05))
                y_offset += point_offset * influence
        current_y = start_y + y_offset + random.uniform(-5, 5)
        await mouse.move(target_x, current_y, 1)
        await page.wait_for_timeout(max(1, int(avg_delay + random.uniform(-2.5, 2.5))))
        last_x = target_x

    await page.wait_for_timeout(int(random.uniform(30, 80)))
    overshoot = random.uniform(5, 15)
    await mouse.move(start_x + distance + overshoot, start_y + random.uniform(-20, 20), 1)
    await page.wait_for_timeout(int(random.uniform(40, 90)))
    end_y = start_y + random.uniform(-15, 15)
    await mouse.move(start_x + distance, end_y, 1)
    await page.wait_for_timeout(int(random.uniform(40, 90)))
    await mouse.up(start_x + distance, end_y)


async def _human_physics_drag(
    page: Any,
    mouse: CdpMouse | PageMouseFallback,
    start_x: float,
    start_y: float,
    distance: float,
    attempt: int,
) -> None:
    """最小急动度剖面拖动：平滑钟形速度 + 随机游走噪声 + X 强制不回退。

    基于 Hogan 1984 的人类 reaching 运动最优模型（10·t³ - 15·t⁴ + 6·t⁵）。
    总时长 0.7-1.3s、步数 100-140，接近 125Hz 鼠标采样率。
    """
    sx = start_x + random.uniform(-0.5, 0.5)
    sy = start_y + random.uniform(-0.5, 0.5)
    dist = distance + random.uniform(-1.0, 1.0)
    total_ms = random.uniform(700, 1300)
    steps = random.randint(100, 140)
    avg_delay = total_ms / steps
    y_drift_amp = random.uniform(2.0, 5.0)
    y_drift_phase = random.uniform(0, math.tau)
    tremor_amp = random.uniform(0.5, 1.5)
    pause_positions = sorted(random.sample([0.15, 0.35, 0.55, 0.75], random.randint(1, 2)))
    pause_idx = 0
    overshoot_px = random.uniform(2, 6)
    overshoot_pause_ms = int(random.uniform(40, 100))
    noise_accum = 0.0
    last_x = sx

    for index in range(1, steps + 1):
        t = index / steps
        jerk = 10 * t**3 - 15 * t**4 + 6 * t**5
        noise_accum += random.uniform(-0.12, 0.12)
        noise_accum = max(-1.2, min(1.2, noise_accum))
        target_x = sx + dist * jerk + noise_accum
        if target_x < last_x:
            target_x = last_x + random.uniform(0.1, 0.5)
        target_x += random.uniform(-0.2, 0.2)
        y_drift = math.sin(t * math.pi + y_drift_phase) * y_drift_amp * 0.3
        y_tremor = random.uniform(-1, 1) * tremor_amp
        if t > 0.7:
            y_tremor *= 1.0 - ((t - 0.7) / 0.3) * 0.5
        target_y = sy + y_drift + y_tremor
        await mouse.move(target_x, target_y, 1)
        delay = max(3, avg_delay + random.uniform(-3.5, 3.5))
        await page.wait_for_timeout(max(1, int(delay)))
        last_x = target_x
        if pause_idx < len(pause_positions) and t >= pause_positions[pause_idx]:
            pause_idx += 1
            pause_ms = int(random.uniform(30, 80))
            pause_steps = max(1, pause_ms // 30)
            for _ in range(pause_steps):
                p_drift = math.sin(t * math.pi + y_drift_phase) * y_drift_amp * 0.3
                await mouse.move(
                    last_x + random.uniform(-0.4, 0.4),
                    sy + p_drift + random.uniform(-0.6, 0.6),
                    1,
                )
                await page.wait_for_timeout(int(random.uniform(25, 35)))

    end_x = sx + dist
    await mouse.move(end_x + overshoot_px, sy + random.uniform(-1, 1), 1)
    await page.wait_for_timeout(overshoot_pause_ms)
    for _ in range(random.randint(2, 3)):
        await mouse.move(end_x + random.uniform(-0.8, 0.8), sy + random.uniform(-1, 1), 1)
        await page.wait_for_timeout(int(random.uniform(40, 120)))
    # 释放前 Y 微微上移（人类松手时手会自然抬起）
    await mouse.move(end_x + random.uniform(-0.5, 0.5), sy - 2 + random.uniform(-1, 1), 1)
    await page.wait_for_timeout(int(random.uniform(150, 350)))
    await mouse.up(end_x + random.uniform(-0.5, 0.5), sy - 2 + random.uniform(-1, 1))
    await page.wait_for_timeout(int(random.uniform(80, 200)))


async def _simulate_slide(
    page: Any,
    button: Any,
    scope: Any,
    distance: float,
    attempt: int,
    *,
    prefer_page_mouse: bool = False,
) -> bool:
    """接近滑块 → 按下 → 按策略拖动 → 释放。

    @param page Playwright Page
    @param button 滑块按钮
    @param scope 滑块所在 frame / page
    @param distance 可滑动距离
    @param attempt 尝试序号（决定轨迹策略）
    @param prefer_page_mouse Camoufox 等强制走 page.mouse
    @returns 是否完成拖动动作
    """
    box = await button.bounding_box()
    if not box:
        return False
    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2

    # 接近轨迹：从按钮附近随机点移入（非瞬移到按钮中心）
    angle = random.uniform(0, math.tau)
    approach_dist = random.uniform(40, 120)
    approach_x = start_x + math.cos(angle) * approach_dist
    approach_y = start_y + math.sin(angle) * approach_dist
    await page.mouse.move(approach_x, approach_y, steps=random.randint(5, 8))
    await page.wait_for_timeout(int(random.uniform(80, 200)))
    approach_steps = random.randint(3, 5)
    for index in range(1, approach_steps + 1):
        t = index / approach_steps
        eased = t * t * (3 - 2 * t)
        await page.mouse.move(
            approach_x + (start_x - approach_x) * eased,
            approach_y + (start_y - approach_y) * eased,
            steps=4,
        )
        await page.wait_for_timeout(int(random.uniform(10, 35)))
    # 移到按钮后的"思考"停顿
    await page.wait_for_timeout(int(random.uniform(100, 250)))

    mouse = await _create_drag_mouse(page, start_x, start_y, prefer_page_mouse=prefer_page_mouse)
    await mouse.down(start_x, start_y)
    await page.wait_for_timeout(int(random.uniform(80, 180)))
    # 按下后微小漂移（真人按下到开始拖动之间鼠标常有 1-2px 漂移）
    await mouse.move(
        start_x + random.uniform(-1.5, 1.5),
        start_y + random.uniform(-1.5, 1.5),
        3,
    )
    await page.wait_for_timeout(int(random.uniform(30, 80)))

    strategy = _strategy_for_attempt(attempt)
    if strategy == 0:
        await _human_physics_drag(page, mouse, start_x, start_y, distance, attempt)
    elif strategy == 1:
        await _human_like_drag(page, mouse, start_x, start_y, distance, attempt)
    else:
        await _human_like_drag_out(page, mouse, start_x, start_y, distance, attempt)
    return True


async def _has_fail_marker(scope: Any) -> bool:
    """检测明确的失败 / 重试标识（Baxia 标准类名）。"""
    for selector in FAIL_SELECTORS:
        try:
            element = await scope.query_selector(selector)
            if element is not None and await element.is_visible():
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _verification_ok(page: Any, scope: Any, cookies: list[dict[str, Any]]) -> bool:
    """判断滑块是否已通过。

    @param page Playwright Page
    @param scope 滑块所在 frame / page
    @param cookies 当前 Cookie
    @returns 通过返回 True
    """
    url = (page.url or "").lower()
    if "chrome-error://" in url or "chromewebdata" in url:
        return False

    if has_x5sec(cookies):
        return True

    for selector in SUCCESS_SELECTORS:
        try:
            element = await scope.query_selector(selector)
            if element is not None and await element.is_visible():
                return True
        except Exception:  # noqa: BLE001
            continue

    # 弹窗消失即通过；Baxia 验证中容器仍可见
    try:
        container = await scope.query_selector(".nc-container")
        if container is None:
            return True
        if not await container.is_visible():
            return True
    except Exception as error:  # noqa: BLE001
        message = str(error).lower()
        if "detached" in message or "disconnected" in message:
            return True
    return False


async def _wait_for_result(page: Any, scope: Any, context: Any) -> bool:
    """拖动后轮询验证结果：成功即返回，明确失败立即返回。

    Baxia 验证可能需要 3-9s，且会先出现转圈加载，不能只看 1 次快照。
    优先等 ``x5sec``；仅容器消失时再多等片刻，避免导航到淘宝时过早判定成功。
    """
    deadline = time.monotonic() + 9.0
    container_gone_at: float | None = None
    while time.monotonic() < deadline:
        cookies = await context.cookies()
        if has_x5sec(cookies):
            return True
        if await _has_fail_marker(scope):
            return False
        # 容器消失可能只是跳转中，再等最多 2s 看 x5sec
        try:
            container = await scope.query_selector(".nc-container")
            gone = container is None or not await container.is_visible()
        except Exception as error:  # noqa: BLE001
            message = str(error).lower()
            gone = "detached" in message or "disconnected" in message
        if gone:
            if container_gone_at is None:
                container_gone_at = time.monotonic()
            elif time.monotonic() - container_gone_at >= 2.0 and await _verification_ok(
                page, scope, cookies
            ):
                return True
        await page.wait_for_timeout(400)
    cookies = await context.cookies()
    return await _verification_ok(page, scope, cookies)


async def _click_retry(scope: Any) -> None:
    """点击刷新 / 重试按钮以重置滑块。"""
    for selector in RETRY_SELECTORS:
        try:
            element = await scope.query_selector(selector)
            if element and await element.is_visible():
                await element.click(timeout=2000)
                return
        except Exception:  # noqa: BLE001
            continue


def _page_is_punish(page: Any) -> bool:
    """页面 URL 是否处于风控 / 验证码状态。"""
    url = (page.url or "").lower()
    return any(token in url for token in ("punish", "captcha", "_____tmd_____"))


async def try_solve_slider(
    page: Any,
    context: Any,
    *,
    max_retries: int = 3,
    prefer_page_mouse: bool = False,
) -> tuple[bool, str]:
    """在已打开的验证页上自动拖滑块。

    对齐商业版：最多重试 max_retries 次，每次轮换轨迹策略；成功以 x5sec、
    成功标识或弹窗消失为准；失败时清 risk cookies 再刷新重试。

    @param page Playwright Page
    @param context BrowserContext（用于读 Cookie）
    @param max_retries 最大尝试次数
    @param prefer_page_mouse Camoufox 路径强制 page.mouse（避免 CDP）
    @returns (成功, 说明)
    """
    await page.wait_for_timeout(800)

    for attempt in range(1, max_retries + 1):
        logger.info("自动滑块第 %s/%s 次尝试", attempt, max_retries)
        if attempt > 1:
            await page.wait_for_timeout(int(random.uniform(500, 1000)))

        button, track, scope = None, None, None
        for _wait in range(8):
            button, track, scope = await find_slider(page)
            if button is not None and scope is not None:
                break
            await page.wait_for_timeout(400)

        if button is None or scope is None:
            if not _page_is_punish(page):
                # 未处于风控页且无滑块，说明无需验证（续期健康 cookie 场景）
                return True, "无需滑块（未处于风控页）"
            logger.warning("未找到滑块元素")
            await page.wait_for_timeout(1000)
            continue

        distance = await _slide_distance(button, track, scope)
        if distance <= 10:
            logger.warning("滑动距离无效: %s", distance)
            continue

        logger.info(
            "滑动距离=%.1fpx 轨迹=%s",
            distance,
            STRATEGY_NAMES[_strategy_for_attempt(attempt)],
        )
        if not await _simulate_slide(
            page,
            button,
            scope,
            distance,
            attempt,
            prefer_page_mouse=prefer_page_mouse,
        ):
            logger.warning("拖动模拟失败")
            continue

        if await _wait_for_result(page, scope, context):
            logger.info("自动滑块验证成功")
            return True, "自动滑块验证成功"

        logger.warning("第 %s 次滑块未通过，清理 risk cookies 后重试", attempt)
        await clear_risk_cookies(context)
        await _click_retry(scope)

    return False, f"自动滑块失败（已尝试 {max_retries} 次）"
