"""1688 扫码登录（对齐 1688-cli：signin 页 + qrcode/generate API 拦截）。

拦截二维码生成/状态接口，将会话进度映射为统一 QR 状态机供 Rust/UI 轮询。"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import re
import time
from typing import Any

import segno

from crawlers.alibaba.browser import Ali1688Browser
from crawlers.core.login.helpers import has_login_cookie, to_qr_data_url
from crawlers.core.login.qrcode import QrcodeLogin
from crawlers.core.login.session import QR_REFRESH_SECONDS, QR_WAIT_TIMEOUT_MS, QrSession

logger = logging.getLogger("dingda.sidecar.qr")

_QR_GENERATE_PATTERN = re.compile(r"qrcode/generate", re.I)
_QR_STATUS_PATTERN = re.compile(
    r"qrcode/(?:query|login|check)|qrcodeLoginCheck|qrcodelogin",
    re.I,
)
_QR_CODE_IN_TEXT = re.compile(r"""['"]?code['"]?\s*[:=]\s*['"]?(\d+)""", re.I)
_PROGRESS_RANK = {"scanned": 1, "confirmed": 2}


def find_code_content(payload: Any) -> str | None:
    """递归查找 JSON 响应中的 codeContent。"""
    if isinstance(payload, dict):
        raw = payload.get("codeContent")
        if raw:
            return str(raw)
        for value in payload.values():
            found = find_code_content(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = find_code_content(item)
            if found:
                return found
    return None


def parse_qr_login_status(payload: Any) -> str | None:
    """解析 QR 轮询响应：scanned / confirmed / expired。"""
    if isinstance(payload, dict):
        if payload.get("success") and payload.get("url"):
            return "confirmed"
        code = payload.get("code")
        if code is not None:
            return _map_qr_status_code(code)
        data = payload.get("data")
        if isinstance(data, dict):
            nested = parse_qr_login_status(data)
            if nested:
                return nested
    if isinstance(payload, str):
        lowered = payload.lower()
        if "window.code=201" in lowered or re.search(r"\bcode=201\b", lowered):
            return "scanned"
        if "window.code=200" in lowered or re.search(r"\bcode=200\b", lowered):
            return "confirmed"
        if "window.code=400" in lowered or re.search(r"\bcode=400\b", lowered):
            return "expired"
        match = _QR_CODE_IN_TEXT.search(payload)
        if match:
            return _map_qr_status_code(match.group(1))
    return None


def _map_qr_status_code(code: Any) -> str | None:
    value = str(code).strip()
    if value in {"201", "10001"}:
        return "scanned"
    if value in {"200", "10006"}:
        return "confirmed"
    if value in {"400"}:
        return "expired"
    return None


def _set_qr_progress(session: QrSession, progress: str) -> None:
    current = session.qr_progress
    if current is None or _PROGRESS_RANK.get(progress, 0) > _PROGRESS_RANK.get(current, 0):
        session.qr_progress = progress
        logger.info("1688 扫码进度 progress=%s", progress)


def render_code_content_to_data_url(content: str) -> str:
    qr = segno.make(content)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=8, border=2)
    return to_qr_data_url(buf.getvalue())


class Ali1688Qrcode(QrcodeLogin):
    """1688 扫码：直连 signin 页，拦截 qrcode/generate 生成 QR。"""

    def __init__(self) -> None:
        super().__init__(Ali1688Browser())

    async def _parse_response_body(self, response: Any) -> Any:
        with contextlib.suppress(Exception):
            return await response.json()
        with contextlib.suppress(Exception):
            text = await response.text()
            with contextlib.suppress(json.JSONDecodeError):
                return json.loads(text)
            return text
        return None

    def _attach_qr_listener(self, page: Any, session: QrSession) -> None:
        async def handle_response(response: Any) -> None:
            url = str(response.url)
            body = await self._parse_response_body(response)
            if _QR_GENERATE_PATTERN.search(url):
                with contextlib.suppress(Exception):
                    content = find_code_content(body)
                    if not content or content == session.qr_code_content:
                        return
                    session.qr_code_content = content
                    session.qr_base64 = render_code_content_to_data_url(content)
                    logger.info(
                        "1688 从 qrcode/generate 获取 QR content_len=%s",
                        len(content),
                    )
                return

            if not _QR_STATUS_PATTERN.search(url):
                return
            progress = parse_qr_login_status(body)
            if progress:
                _set_qr_progress(session, progress)

        def on_response(response: Any) -> None:
            asyncio.create_task(handle_response(response))

        page.on("response", on_response)

    async def _before_login_goto(self, page: Any, session: QrSession) -> None:
        self._attach_qr_listener(page, session)

    async def _login_progress(
        self,
        session: QrSession,
        page: Any,
        cookies: list[dict[str, Any]],
    ) -> str | None:
        progress = session.qr_progress
        if progress == "expired":
            return "expired"
        if progress in {"scanned", "confirmed"}:
            return progress

        page_text = await self._collect_login_page_text(page)
        from crawlers.core.login.helpers import login_progress_from_text

        return login_progress_from_text(page_text)

    async def _collect_login_page_text(self, page: Any) -> str:
        from crawlers.core.login.helpers import collect_page_text

        chunks = [await collect_page_text(page)]
        with contextlib.suppress(Exception):
            for frame in page.frames:
                url = str(frame.url).lower()
                if "login" not in url and "passport" not in url and "1688" not in url:
                    continue
                with contextlib.suppress(Exception):
                    text = (await frame.locator("body").inner_text(timeout=1200))[:400]
                    if text.strip():
                        chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk)[:2000]

    async def _capture_qr(self, page: Any, session: QrSession) -> str | None:
        deadline = time.monotonic() + QR_WAIT_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            if session.qr_base64 and session.qr_code_content:
                session.last_emitted_qr_content = session.qr_code_content
                return session.qr_base64
            await page.wait_for_timeout(300)
        if session.qr_base64:
            session.last_emitted_qr_content = session.qr_code_content
        return session.qr_base64

    async def _poll_passive_qr_update(self, session: QrSession) -> str | None:
        content = session.qr_code_content
        if content and content != session.last_emitted_qr_content and session.qr_base64:
            session.last_emitted_qr_content = content
            return session.qr_base64
        return None

    async def _needs_qr_refresh(self, session: QrSession, page: Any) -> bool:
        return time.monotonic() - session.last_refresh_at > QR_REFRESH_SECONDS

    async def _refresh(self, session: QrSession) -> str | None:
        page = session.page
        if page is None:
            logger.warning("1688 二维码刷新失败：浏览器会话已关闭")
            return None
        old_content = session.qr_code_content
        config = self.config
        try:
            await page.goto(
                config.login_entry_url,
                wait_until="domcontentloaded",
                timeout=40000,
            )
            await page.wait_for_timeout(800)
            deadline = time.monotonic() + QR_WAIT_TIMEOUT_MS / 1000
            while time.monotonic() < deadline:
                if session.qr_code_content and session.qr_code_content != old_content:
                    session.last_emitted_qr_content = session.qr_code_content
                    logger.info("1688 二维码已刷新")
                    return session.qr_base64
                await page.wait_for_timeout(300)
            if session.qr_base64:
                session.last_emitted_qr_content = session.qr_code_content
                return session.qr_base64
            logger.warning("1688 二维码刷新失败：未收到新 codeContent")
            return None
        except Exception as error:  # noqa: BLE001
            logger.warning("1688 二维码刷新失败：%s", str(error)[:160])
            return None

    async def _warm_home(self, session: QrSession) -> None:
        page = session.page
        if page is None:
            return
        await self._goto(page, self.config.home_url, wait_ms=3000)

    def _export_indicates_login(
        self,
        cookies: list[dict[str, Any]],
        *,
        page_url: str | None,
    ) -> bool:
        return has_login_cookie(
            cookies,
            name=self.config.login_cookie_name,
            domain_keyword=self.config.cookie_domain_keyword,
        )

    async def _probe_logged_in(
        self,
        session: QrSession,
        page: Any,
        cookies: list[dict[str, Any]],
    ) -> bool:
        config = self.config
        if has_login_cookie(
            cookies,
            name=config.login_cookie_name,
            domain_keyword=config.cookie_domain_keyword,
        ):
            return True
        if session.qr_progress != "confirmed":
            return False
        if not config.sso_cookie_name or not config.sso_cookie_domain_keyword:
            return False
        return has_login_cookie(
            cookies,
            name=config.sso_cookie_name,
            domain_keyword=config.sso_cookie_domain_keyword,
        )
