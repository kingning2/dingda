"""闲鱼 Passport 扫码登录 API 原语。

职责：
    提供二维码拉取、登录态 cookie 检测等底层能力；经 browser.sync 开无头页，
    不含扫码状态机与账号持久化。

设计说明：
    - 平台：闲鱼（xianyu）
    - 供 XianyuChannel 登录流程调用，不直接暴露给 Tool / Agent
    - 登录完成判定依赖 REQUIRED_LOGIN_COOKIES 与 baseline 对比
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any
from urllib.request import urlopen

from src.browser.sync import sync_headless_page
from src.channels.xianyu.cookies import cookie_map

logger = logging.getLogger("dingda.channel.xianyu.api")

HOME_URL = "https://www.goofish.com/login"
REQUIRED_LOGIN_COOKIES = ("_m_h5_tk", "unb", "cookie2")
SCANNED_COOKIE_HINTS = ("unb", "cookie2")

QR_REFRESH_INTERVAL_S = 110
QR_MAX_REFRESHES = 10


def cookie_str(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def has_all_login_cookies(cookies_list: list[dict[str, Any]]) -> bool:
    names = set(cookie_map(cookies_list))
    return all(key in names for key in REQUIRED_LOGIN_COOKIES)



def has_login_completed(
    cookies_list: list[dict[str, Any]],
    baseline: dict[str, str],
) -> bool:
    """完整 session cookie 到位，且相对二维码就绪时有新增（避免残留登录态误判）。"""
    current = cookie_map(cookies_list)
    if not all(key in current for key in REQUIRED_LOGIN_COOKIES):
        return False
    for key in ("unb", "cookie2"):
        value = current.get(key)
        if not value or value == baseline.get(key):
            return False
    return True


def has_scanned_cookies(
    cookies_list: list[dict[str, Any]],
    baseline: dict[str, str],
) -> bool:
    """扫码后 passport 常会先下发部分 cookie，再等待手机确认。"""
    if has_login_completed(cookies_list, baseline):
        return False
    current = cookie_map(cookies_list)
    for name in SCANNED_COOKIE_HINTS:
        value = current.get(name)
        if value and value != baseline.get(name):
            return True
    return False


def find_passport_frame(page: Any, timeout_ms: int = 20_000) -> Any:
    import time

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "passport" in (frame.url or ""):
                return frame
        time.sleep(0.5)
    return None


def wait_for_qr_frame(page: Any, timeout_ms: int = 15_000) -> Any:
    frame = find_passport_frame(page)
    if not frame:
        return None
    try:
        frame.wait_for_selector(".qrcode-login", timeout=timeout_ms)
        return frame
    except Exception:
        return None


def normalize_qr_base64(src: str) -> tuple[str | None, str | None]:
    src = src.strip()
    if not src:
        return None, None
    if src.startswith("data:image"):
        _, _, payload = src.partition(",")
        return (payload or None), None
    if src.startswith("http://") or src.startswith("https://"):
        try:
            with urlopen(src, timeout=10) as response:
                return base64.b64encode(response.read()).decode("ascii"), src
        except Exception:
            return None, src
    return None, None


def capture_qr(frame: Any) -> tuple[str | None, str | None]:
    """从登录 iframe 截取二维码图（含远程图片下载或本地截图）。"""
    started = time.perf_counter()
    image = frame.query_selector(".qrcode-img")
    if not image:
        return None, None
    src = image.get_attribute("src")
    if isinstance(src, str) and src.strip():
        encoded, qr_url = normalize_qr_base64(src)
        if encoded:
            elapsed = time.perf_counter() - started
            logger.info(
                "闲鱼二维码截取完成 elapsed=%.2fs elapsed_ms=%d",
                elapsed,
                int(elapsed * 1000),
            )
            return encoded, qr_url or src
    try:
        png = image.screenshot(type="png")
        elapsed = time.perf_counter() - started
        logger.info(
            "闲鱼二维码截图完成 elapsed=%.2fs elapsed_ms=%d",
            elapsed,
            int(elapsed * 1000),
        )
        return base64.b64encode(png).decode("ascii"), None
    except Exception:
        return None, None


def open_login_page():
    """Context manager：打开闲鱼登录页并返回 (page, passport_frame)。"""
    return _LoginPageSession()


class _LoginPageSession:
    def __enter__(self):
        self._ctx = sync_headless_page()
        self.page = self._ctx.__enter__()
        # 干净上下文：避免 Camoufox 残留登录态导致未扫码即判成功（对齐 goofish_cli cookies={}）
        self.page.context.clear_cookies()
        self.page.goto(HOME_URL, wait_until="domcontentloaded", timeout=20_000)
        self.page.wait_for_timeout(1500)
        self.frame = wait_for_qr_frame(self.page)
        if not self.frame:
            raise RuntimeError("未检测到闲鱼扫码区域，请稍后重试")
        return self.page, self.frame

    def __exit__(self, exc_type, exc, tb):
        return self._ctx.__exit__(exc_type, exc, tb)
