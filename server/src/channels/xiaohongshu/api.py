"""小红书扫码 API 原语。"""

from __future__ import annotations

import base64
import io
import logging
import time
from typing import Any

from src.browser.context import cookies_to_playwright
from src.channels.profile_fields import extract_profile_from_tree
from src.channels.xiaohongshu.cookies import to_browser_cookies

logger = logging.getLogger("dingda.channel.xiaohongshu.api")

LOGIN_URL = "https://www.xiaohongshu.com/login"
HOME_URL = "https://www.xiaohongshu.com"
QR_CREATE_ENDPOINT = "/api/sns/web/v1/login/qrcode/create"
QR_USERINFO_ENDPOINT = "/api/qrcode/userinfo"
QR_STATUS_ENDPOINT = "/api/sns/web/v1/login/qrcode/status"
QR_STATUS_URL = f"https://edith.xiaohongshu.com{QR_STATUS_ENDPOINT}"
BROWSER_EXPORT_COOKIE_NAMES = {
    "a1",
    "webId",
    "web_session",
    "web_session_sec",
    "id_token",
    "websectiga",
    "sec_poison_id",
    "xsecappid",
    "gid",
    "abRequestId",
    "webBuild",
    "loadts",
}
REQUIRED_COOKIES = {"a1", "web_session"}

# codeStatus: 0=未扫 1=已扫待确认 2=成功 3=过期（见 xhs 扫码协议）
QR_STATUS_EXPIRED = 3
QR_MAX_REFRESHES = 10

REFRESH_SELECTORS = (
    "text=点击刷新",
    "text=刷新二维码",
    "text=刷新",
    ".refresh-qrcode",
    "[class*='refresh']",
)


def is_qr_expired(code_status: int) -> bool:
    return code_status == QR_STATUS_EXPIRED


def extract_qr_url(payload: dict[str, Any]) -> str:
    return str(payload.get("url", "")).strip()


def parse_code_status(payload: dict[str, Any]) -> int:
    raw = payload.get("code_status", payload.get("codeStatus", -1))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def qr_png_base64(url: str) -> str | None:
    """把扫码 URL 画成 PNG base64，给前端 img 用。"""
    started = time.perf_counter()
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    elapsed = time.perf_counter() - started
    logger.info(
        "小红书二维码 PNG 已生成 elapsed=%.2fs elapsed_ms=%d",
        elapsed,
        int(elapsed * 1000),
    )
    return encoded


def unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def browser_payload(response: Any) -> dict[str, Any]:
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("unexpected QR payload")
    return unwrap_payload(data)


def normalize_cookies(raw_cookies: list[dict[str, Any]]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for entry in raw_cookies:
        name = entry.get("name")
        value = entry.get("value")
        domain = entry.get("domain", "")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        if name not in BROWSER_EXPORT_COOKIE_NAMES:
            continue
        if not isinstance(domain, str) or "xiaohongshu.com" not in domain:
            continue
        cookies[name] = value
    return cookies


def cookie_str(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _matches_qr_create(response: Any) -> bool:
    return QR_CREATE_ENDPOINT in response.url and response.request.method == "POST"


def apply_qr_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """从 create 响应解析 qr_url 与 png base64。"""
    qr_url = extract_qr_url(payload)
    if not qr_url:
        return None, None
    return qr_url, qr_png_base64(qr_url)


def is_status_poll_response(response: Any) -> bool:
    return QR_STATUS_ENDPOINT in response.url and response.request.method in {
        "GET",
        "POST",
    }


def response_code_status(response: Any) -> int:
    try:
        return parse_code_status(browser_payload(response))
    except Exception:
        return -1


def is_login_success_response(response: Any) -> bool:
    if not is_status_poll_response(response):
        return False
    return response_code_status(response) == 2


def profile_from_user_me(payload: dict[str, Any]) -> dict[str, Any]:
    """把 user/me 的 data 转成 display 字段：nickname / images / user_id。"""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        logger.info("user/me 解析跳过：payload 不是对象 type=%s", type(payload).__name__)
        return {}
    if data.get("guest") is True:
        logger.info("user/me 仍是 guest keys=%s", sorted(data.keys()))
        return {}
    nickname = str(data.get("nickname") or "").strip() or None
    avatar_url = str(data.get("images") or data.get("imageb") or "").strip() or None
    user_id = str(data.get("user_id") or data.get("userId") or "").strip() or None
    logger.info(
        "user/me 字段 nickname=%s user_id=%s images=%s guest=%s keys=%s",
        nickname,
        user_id,
        (avatar_url[:80] + "…") if avatar_url and len(avatar_url) > 80 else avatar_url,
        data.get("guest"),
        sorted(data.keys()),
    )
    profile: dict[str, Any] = {}
    if nickname:
        profile["nickname"] = nickname
    if avatar_url:
        profile["avatar_url"] = avatar_url
    if user_id:
        profile["user_id"] = user_id
    return profile


def apply_session_cookies(page: Any, cookies: dict[str, str]) -> None:
    """把扫码 JSON 里的 session 写进当前浏览器，供随后打开探索页。"""
    page.context.add_cookies(cookies_to_playwright(to_browser_cookies(cookies)))


_READ_USER_INFO_JS = """
() => {
    const state = window.__INITIAL_STATE__;
    if (!state || !state.user) {
        return { __error: "no __INITIAL_STATE__.user" };
    }
    const raw = state.user.userInfo;
    const info = raw && raw.value !== undefined ? raw.value : raw;
    if (!info) {
        return { __error: "no userInfo" };
    }
    return info;
}
"""


def read_page_user_info(page: Any) -> dict[str, Any]:
    """从探索页 ``__INITIAL_STATE__.user.userInfo`` 读当前登录用户（对齐 xiaohongshu-mcp）。"""
    page.wait_for_function(
        "() => window.__INITIAL_STATE__ !== undefined",
        timeout=15_000,
    )
    raw = page.evaluate(_READ_USER_INFO_JS)
    logger.info(
        "userInfo evaluate type=%s keys=%s error=%s",
        type(raw).__name__,
        sorted(raw.keys()) if isinstance(raw, dict) else None,
        raw.get("__error") if isinstance(raw, dict) else None,
    )
    if not isinstance(raw, dict) or raw.get("__error"):
        return {}
    return profile_from_user_me(raw)


def read_login_profile(
    page: Any,
    cookies: dict[str, str],
) -> dict[str, Any]:
    """登录成功后打开探索页，从页面状态读昵称头像。"""
    logger.info(
        "userInfo 开始读取 page=%s cookie_keys=%s has_a1=%s has_web_session=%s",
        getattr(page, "url", ""),
        sorted(cookies.keys()),
        bool(cookies.get("a1")),
        bool(cookies.get("web_session")),
    )
    apply_session_cookies(page, cookies)
    try:
        logger.info("打开探索页读取 __INITIAL_STATE__")
        page.goto(f"{HOME_URL}/explore", wait_until="domcontentloaded", timeout=25_000)
        page.wait_for_timeout(1_000)
        logger.info("探索页已打开 page=%s", getattr(page, "url", ""))
        profile = read_page_user_info(page)
        logger.info(
            "userInfo 读取完成 name=%s avatar=%s user_id=%s",
            profile.get("nickname"),
            bool(profile.get("avatar_url")),
            profile.get("user_id"),
        )
        return profile
    except Exception as exc:
        logger.info("userInfo 读取失败: %s page=%s", exc, getattr(page, "url", ""))
        return {}


def merge_session_cookies(
    cookies: dict[str, str],
    completion_data: dict[str, Any],
) -> dict[str, str]:
    login_info = completion_data.get("login_info", {})
    if not isinstance(login_info, dict):
        login_info = {}

    session = login_info.get("session") or completion_data.get("session")
    secure_session = login_info.get("secure_session") or completion_data.get(
        "secure_session"
    )
    if isinstance(session, str) and session:
        cookies["web_session"] = session
    if isinstance(secure_session, str) and secure_session:
        cookies["web_session_sec"] = secure_session
    return cookies


def collect_login_cookies(page: Any, completion_data: dict[str, Any]) -> dict[str, str]:
    """扫码确认后收集完整 cookie：先快取，不足再短暂等待重试。"""
    import time

    cookies = normalize_cookies(page.context.cookies())
    cookies = merge_session_cookies(cookies, completion_data)
    if REQUIRED_COOKIES.issubset(cookies.keys()):
        return cookies

    time.sleep(0.3)
    for attempt in range(4):
        cookies = normalize_cookies(page.context.cookies())
        cookies = merge_session_cookies(cookies, completion_data)
        if REQUIRED_COOKIES.issubset(cookies.keys()):
            return cookies
        logger.debug(
            "小红书 cookie 未齐全，重试 %s/4 keys=%s",
            attempt + 1,
            sorted(cookies.keys()),
        )
        time.sleep(0.3)

    missing = sorted(REQUIRED_COOKIES - set(cookies.keys()))
    raise ValueError(f"登录成功但 cookie 不完整，缺少: {', '.join(missing)}")


def publish_login_success(
    runtime: Any,
    page: Any,
    completion_data: dict[str, Any],
) -> tuple[str, str, str | None, str]:
    """写入 runtime 登录结果；先落 cookie 再读探索页资料，避免前端仍显示二维码。"""
    logger.info("小红书登录确认，开始收 cookie 并从探索页读 userInfo")
    cookies = collect_login_cookies(page, completion_data)
    logger.info("小红书 cookie 已收集 keys=%s", sorted(cookies.keys()))
    account_id, display_name, avatar_url = build_account_profile(
        cookies,
        completion_data,
        None,
    )
    serialized = cookie_str(cookies)
    # 先写 cookie，轮询立刻变 success；昵称头像稍后补
    with runtime.lock:
        runtime.cookie = serialized
        runtime.account_id = account_id
        runtime.display_name = display_name
        runtime.avatar_url = avatar_url
        runtime.code_status = 2
    logger.info(
        "小红书登录态已写入 cookie account_id=%s，继续读资料",
        account_id,
    )

    settled_profile = read_login_profile(page, cookies)
    if settled_profile:
        account_id, display_name, avatar_url = build_account_profile(
            cookies,
            completion_data,
            settled_profile,
        )
        with runtime.lock:
            runtime.account_id = account_id
            runtime.display_name = display_name
            runtime.avatar_url = avatar_url
    logger.info(
        "小红书资料写入 account_id=%s name=%s avatar=%s",
        account_id,
        display_name,
        bool(avatar_url),
    )
    return account_id, display_name, avatar_url, serialized


def build_account_profile(
    cookies: dict[str, str],
    completion_data: dict[str, Any],
    settled_profile: dict[str, Any] | None = None,
) -> tuple[str, str, str | None]:
    login_info = completion_data.get("login_info", {})
    if not isinstance(login_info, dict):
        login_info = {}
    settled = settled_profile or {}

    nickname = str(settled.get("nickname") or "").strip() or None
    avatar_url = str(settled.get("avatar_url") or "").strip() or None
    if not nickname or not avatar_url:
        tree_name, tree_avatar = extract_profile_from_tree(
            {"login_info": login_info, **completion_data}
        )
        nickname = nickname or tree_name
        avatar_url = avatar_url or tree_avatar

    user_id = (
        settled.get("user_id")
        or login_info.get("user_id")
        or completion_data.get("user_id")
    )
    account_id = (
        f"xhs:{user_id}"
        if user_id
        else f"xhs:{cookies.get('web_session', 'unknown')[:12]}"
    )
    display_name = (nickname or "").strip() or "新小红书账号"
    return account_id, display_name, avatar_url


def extract_qr_credentials(payload: dict[str, Any]) -> tuple[str, str]:
    qr_id = str(payload.get("qr_id", "")).strip()
    code = str(payload.get("code", "")).strip()
    return qr_id, code


def poll_status_in_browser(page: Any, qr_id: str, code: str) -> dict[str, Any]:
    """在页面上下文主动轮询扫码状态（复用站点签名，不依赖被动 response 监听）。"""
    raw = page.evaluate(
        """
        async ({ statusUrl, qrId, qrCode }) => {
            const url = `${statusUrl}?qr_id=${encodeURIComponent(qrId)}&code=${encodeURIComponent(qrCode)}`;
            const resp = await fetch(url, {
                method: 'GET',
                credentials: 'include',
            });
            if (!resp.ok) {
                return { __error: `HTTP ${resp.status}` };
            }
            return await resp.json();
        }
        """,
        {"statusUrl": QR_STATUS_URL, "qrId": qr_id, "qrCode": code},
    )
    if not isinstance(raw, dict):
        raise ValueError("status 轮询返回非 JSON 对象")
    if raw.get("__error"):
        raise ValueError(str(raw["__error"]))
    return unwrap_payload(raw)


def apply_status_payload(
    payload: dict[str, Any],
    *,
    runtime: Any,
    expired_pending: dict[str, bool],
    completion_holder: dict[str, Any],
    login_complete: Any,
) -> int:
    """处理 status 响应，返回 code_status。"""
    code_status = parse_code_status(payload)
    if is_qr_expired(code_status):
        expired_pending["value"] = True
        logger.info("小红书二维码已过期，准备刷新")
    elif code_status == 1:
        with runtime.lock:
            if runtime.code_status != 1:
                logger.info("小红书二维码已扫描，等待手机确认")
            runtime.code_status = 1
    elif code_status == 2:
        completion_holder["data"] = payload
        with runtime.lock:
            runtime.code_status = 2
        login_complete.set()
        logger.info("小红书扫码登录已确认")
    return code_status


def trigger_qr_refresh(page: Any) -> dict[str, Any]:
    """二维码过期后触发刷新，等待新的 create 响应。"""
    for selector in REFRESH_SELECTORS:
        try:
            locator = page.locator(selector).first
            if locator.count() == 0 or not locator.is_visible():
                continue
            with page.expect_response(_matches_qr_create, timeout=15_000) as response_info:
                locator.click()
            return browser_payload(response_info.value)
        except Exception as exc:
            logger.debug("小红书刷新按钮 %s 失败: %s", selector, exc)

    logger.info("未找到刷新按钮，重新加载小红书登录页")
    with page.expect_response(_matches_qr_create, timeout=20_000) as response_info:
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20_000)
    return browser_payload(response_info.value)
