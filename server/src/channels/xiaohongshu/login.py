"""小红书扫码登录原语。"""

from __future__ import annotations

import base64
import io
import logging
import time
from typing import Any

from src.browser.context import cookies_to_playwright
from src.channels.profile_fields import extract_profile_from_tree
from src.channels.xiaohongshu.cookies import to_browser_cookies

logger = logging.getLogger("dingda.channel.xiaohongshu.login")

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
    user_id = _pick_user_id(data)
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


def _pick_user_id(*sources: Any) -> str | None:
    """从多处 dict 取稳定 user_id（兼容 userId / 嵌套 login_info）。"""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in ("user_id", "userId", "userid"):
            value = src.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = src.get("login_info")
        if isinstance(nested, dict):
            found = _pick_user_id(nested)
            if found:
                return found
    return None


def _has_login_session(payload: dict[str, Any] | None) -> bool:
    """status=2 是否已带上可写入浏览器的 session。"""
    if not isinstance(payload, dict):
        return False
    login_info = payload.get("login_info")
    if isinstance(login_info, dict):
        session = login_info.get("session") or login_info.get("secure_session")
        if isinstance(session, str) and session.strip():
            return True
    session = payload.get("session") or payload.get("secure_session")
    return isinstance(session, str) and bool(session.strip())


def _completion_richness(payload: dict[str, Any]) -> int:
    """status=2 载荷完整度：session > user_id > 其它。"""
    login_info = payload.get("login_info")
    score = 0
    if isinstance(login_info, dict):
        if login_info.get("session") or login_info.get("secure_session"):
            score += 8
        if _pick_user_id(login_info):
            score += 4
        if login_info.get("nickname"):
            score += 1
    if payload.get("session") or payload.get("secure_session"):
        score += 8
    if _pick_user_id(payload):
        score += 4
    return score


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

_USER_INFO_READY_JS = """
() => {
  const raw = window.__INITIAL_STATE__?.user?.userInfo;
  const info = raw && raw.value !== undefined ? raw.value : raw;
  if (!info || info.guest === true) return false;
  return !!(info.nickname || info.user_id || info.userId);
}
"""

_PROFILE_API_NEEDLES = (
    "api/sns/web/v2/user/me",
    "api/sns/web/v1/user/otherinfo",
    "api/sns/web/v1/user/selfinfo",
)


def _is_profile_api_response(response: Any) -> bool:
    try:
        url = response.url or ""
        if response.request.method not in {"GET", "POST"}:
            return False
        return any(needle in url for needle in _PROFILE_API_NEEDLES)
    except Exception:
        return False


def _profile_from_response(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if isinstance(data, dict) and data.get("guest") is True:
        logger.info("忽略 guest 资料响应 keys=%s", sorted(data.keys()))
        return {}
    profile = profile_from_user_me(payload)
    if profile.get("nickname"):
        return profile
    # otherinfo 常见形状：data.basic_info / data.user_info
    if not isinstance(data, dict):
        return profile
    for node in (
        data,
        data.get("basic_info"),
        data.get("basicInfo"),
        data.get("user_info"),
        data.get("userInfo"),
        data.get("user"),
    ):
        if not isinstance(node, dict) or node.get("guest") is True:
            continue
        name, avatar = extract_profile_from_tree(node)
        uid = _pick_user_id(node, data)
        if name or avatar:
            if name:
                profile["nickname"] = name
            if avatar:
                profile["avatar_url"] = avatar
            if uid:
                profile["user_id"] = uid
            if profile.get("nickname"):
                return profile
    return profile


def read_page_user_info(page: Any) -> dict[str, Any]:
    """兼容旧页：若仍有 ``__INITIAL_STATE__`` 则读取（现网多数已不再注入）。"""
    try:
        raw = page.evaluate(_READ_USER_INFO_JS)
    except Exception as exc:  # noqa: BLE001
        logger.info("读取 __INITIAL_STATE__ 失败: %s", exc)
        return {}
    logger.info(
        "userInfo evaluate type=%s keys=%s error=%s",
        type(raw).__name__,
        sorted(raw.keys()) if isinstance(raw, dict) else None,
        raw.get("__error") if isinstance(raw, dict) else None,
    )
    if not isinstance(raw, dict) or raw.get("__error"):
        return {}
    return profile_from_user_me(raw)


def _merge_profile(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for key, value in src.items():
        if value:
            dst[key] = value
    return dst


def _request_user_me_via_context(page: Any) -> dict[str, Any]:
    """用 Playwright 请求上下文读 user/me（同页 cookie，不依赖页面签名脚本）。"""
    try:
        resp = page.request.get(
            "https://edith.xiaohongshu.com/api/sns/web/v2/user/me",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.xiaohongshu.com/",
            },
        )
        payload = resp.json()
        logger.info(
            "context user/me status=%s keys=%s",
            resp.status,
            sorted(payload.keys()) if isinstance(payload, dict) else None,
        )
        if not isinstance(payload, dict):
            return {}
        return profile_from_user_me(payload)
    except Exception as exc:  # noqa: BLE001
        logger.info("context user/me 失败: %s", exc)
        return {}


def _goto_and_catch_profile(page: Any, url: str, *, timeout_ms: int = 15_000) -> dict[str, Any]:
    """导航并截获站点自己发出的资料 XHR（带 x-s 签名）。"""
    best: dict[str, Any] = {}

    def _on_response(response: Any) -> None:
        nonlocal best
        if not _is_profile_api_response(response):
            return
        try:
            got = _profile_from_response(response)
        except Exception:
            return
        if got.get("nickname") or (got.get("user_id") and got.get("avatar_url")):
            _merge_profile(best, got)
            logger.info(
                "截获资料接口 url=%s name=%s user_id=%s",
                (response.url or "")[:120],
                got.get("nickname"),
                got.get("user_id"),
            )

    page.on("response", _on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        deadline = time.monotonic() + timeout_ms / 1000
        me_tried = False
        while time.monotonic() < deadline:
            if best.get("nickname"):
                break
            page.wait_for_timeout(500)
            if not me_tried and not best.get("nickname"):
                me_tried = True
                me = _request_user_me_via_context(page)
                _merge_profile(best, me)
                if best.get("nickname"):
                    break
    except Exception as exc:  # noqa: BLE001
        logger.info("导航读资料失败 url=%s err=%s", url, exc)
    finally:
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            pass
    return best


def read_login_profile(
    page: Any,
    cookies: dict[str, str],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """登录成功后读昵称头像。

    现网多数页面已不再注入 ``__INITIAL_STATE__``，改为截获站点签名 XHR
    （user/me / otherinfo），并短轮询直到出现非 guest 昵称。
    """
    logger.info(
        "userInfo 开始读取 page=%s cookie_keys=%s has_a1=%s has_web_session=%s user_id=%s",
        getattr(page, "url", ""),
        sorted(cookies.keys()),
        bool(cookies.get("a1")),
        bool(cookies.get("web_session")),
        user_id,
    )
    apply_session_cookies(page, cookies)
    merged: dict[str, Any] = {}
    try:
        logger.info("打开探索页并截获资料接口")
        caught = _goto_and_catch_profile(page, f"{HOME_URL}/explore")
        _merge_profile(merged, caught)
        logger.info("探索页已打开 page=%s", getattr(page, "url", ""))

        if not merged.get("nickname"):
            _merge_profile(merged, _request_user_me_via_context(page))

        if not merged.get("nickname"):
            _merge_profile(merged, read_page_user_info(page))

        if not merged.get("nickname") and isinstance(user_id, str) and user_id.strip():
            uid = user_id.strip()
            for url in (
                f"{HOME_URL}/user/profile/me",
                f"{HOME_URL}/user/profile/{uid}",
            ):
                logger.info("改走主页读资料 url=%s", url)
                _merge_profile(merged, _goto_and_catch_profile(page, url, timeout_ms=12_000))
                if merged.get("nickname"):
                    break

        logger.info(
            "userInfo 读取完成 name=%s avatar=%s user_id=%s",
            merged.get("nickname"),
            bool(merged.get("avatar_url")),
            merged.get("user_id"),
        )
        return merged
    except Exception as exc:
        logger.info("userInfo 读取失败: %s page=%s", exc, getattr(page, "url", ""))
        return merged

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
    """写入 runtime 登录结果；先读齐资料再暴露 cookie，避免前端过早落库假 account_id。"""
    logger.info("小红书登录确认，开始收 cookie 并从探索页读 userInfo")
    login_info = completion_data.get("login_info")
    logger.info(
        "completion keys=%s login_info_keys=%s result=%r userId=%s",
        sorted(completion_data.keys()),
        sorted(login_info.keys()) if isinstance(login_info, dict) else None,
        completion_data.get("result"),
        _pick_user_id(completion_data),
    )
    cookies = collect_login_cookies(page, completion_data)
    logger.info("小红书 cookie 已收集 keys=%s", sorted(cookies.keys()))

    known_user_id = _pick_user_id(completion_data)
    # 必须先读资料再写 runtime.cookie：否则轮询会用 web_session 前缀当 account_id 落库
    settled_profile = read_login_profile(page, cookies, user_id=known_user_id)
    account_id, display_name, avatar_url = build_account_profile(
        cookies,
        completion_data,
        settled_profile or None,
    )
    serialized = cookie_str(cookies)
    with runtime.lock:
        runtime.cookie = serialized
        runtime.account_id = account_id
        runtime.display_name = display_name
        runtime.avatar_url = avatar_url
        runtime.code_status = 2
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
        # /api/qrcode/userinfo 的 result 里有时带昵称
        result = completion_data.get("result")
        if isinstance(result, dict) and (not nickname or not avatar_url):
            result_name, result_avatar = extract_profile_from_tree(result)
            nickname = nickname or result_name
            avatar_url = avatar_url or result_avatar
        elif isinstance(result, str) and result.strip() and not nickname:
            # 少数响应 result 直接是昵称字符串
            nickname = result.strip()

    user_id = _pick_user_id(login_info, completion_data, settled)
    if user_id:
        account_id = f"xhs:{user_id}"
    else:
        # 兜底：每次扫码 web_session 都变，会导致重复卡片；尽量不要走到这里
        session = str(cookies.get("web_session") or "unknown")
        account_id = f"xhs:{session[:12]}"
        logger.warning(
            "小红书缺少稳定 user_id，暂用 web_session 前缀 account_id=%s",
            account_id,
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
    """处理 status / userinfo 响应，返回 code_status。

    ``/api/qrcode/userinfo`` 可能先报 codeStatus=2 但没有 ``login_info.session``；
    此时只标记「已确认」，继续等 status 把 session 带下来，否则浏览器仍是 guest。
    """
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
        existing = completion_holder.get("data")
        if not isinstance(existing, dict) or _completion_richness(payload) >= _completion_richness(
            existing
        ):
            completion_holder["data"] = payload
        with runtime.lock:
            runtime.code_status = 2
        if _has_login_session(completion_holder.get("data")):
            login_complete.set()
            logger.info(
                "小红书扫码登录已确认且拿到 session login_info_keys=%s user_id=%s",
                sorted(completion_holder["data"].get("login_info").keys())
                if isinstance(completion_holder["data"].get("login_info"), dict)
                else None,
                _pick_user_id(completion_holder["data"]),
            )
        else:
            logger.info(
                "小红书手机已确认，等待 status 下发 session user_id=%s keys=%s",
                _pick_user_id(payload),
                sorted(payload.keys()),
            )
    return code_status


def wait_for_login_session(
    page: Any,
    *,
    qr_id: str,
    qr_code: str,
    runtime: Any,
    completion_holder: dict[str, Any],
    login_complete: Any,
    expired_pending: dict[str, bool],
    attempts: int = 12,
) -> bool:
    """手机确认后主动轮询 status，直到拿到 login_info.session。"""
    if _has_login_session(completion_holder.get("data")):
        login_complete.set()
        return True
    logger.info("开始补拉 status session qr_id=%s attempts=%s", qr_id, attempts)
    for i in range(1, attempts + 1):
        try:
            status_payload = poll_status_in_browser(page, qr_id, qr_code)
            apply_status_payload(
                status_payload,
                runtime=runtime,
                expired_pending=expired_pending,
                completion_holder=completion_holder,
                login_complete=login_complete,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("补拉 status 失败 attempt=%s/%s err=%s", i, attempts, exc)
        if _has_login_session(completion_holder.get("data")):
            login_complete.set()
            logger.info("补拉 status 成功拿到 session attempt=%s/%s", i, attempts)
            return True
        page.wait_for_timeout(400)
    logger.warning(
        "补拉 status 仍无 session keys=%s",
        sorted((completion_holder.get("data") or {}).keys()),
    )
    return False


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
