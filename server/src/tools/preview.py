"""选品 Tool：preview（打开任意 URL 并直播截图给前端）。

职责：
    Codex 联网搜到网站后调用本工具：Browser 打开页面，截图经 live_hub
    推到当前 Agent run 的 SSE，供前端 PageCard 预览。
    不做 DOM 解析 / 搜品；不替代 search/product。

设计说明：
    - MCP 子进程通过 HTTP 把帧投到 Server（``DINGDA_API_BASE`` + run_id）
    - 本地回调路径（同进程）也可直接 push live_hub
    - 不 import Playwright / Camoufox

使用示例：
    out = await run_preview(PreviewInput(url="https://example.com"))
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from src.browser.manager import get_browser_manager
from src.browser.port import LaunchOptions
from src.crawler.core.live import emit_live_frame, live_frame_pump
from src.crawler.core.types import CrawlContext
from src.shared.errors import AppError
from src.tools.live_push import agent_run_id, post_live_frame

logger = logging.getLogger("dingda.tools.preview")

TOOL_NAME = "preview"
TOOL_DESCRIPTION = (
    "打开任意网页并向前端推送浏览器直播截图（预览用）。"
    "适用：你已用联网搜索找到目标网站/商品页 URL，需要让用户在叮答里看到页面。"
    "不要用本工具替代 search/product（闲鱼/小红书/1688 结构化搜品）。"
    "传入完整 http(s) URL；会短暂停留截图，返回最终 url/title。"
)
DEFAULT_TIMEOUT_S = 45.0
DEFAULT_DURATION_S = 12.0


class PreviewInput(BaseModel):
    """网页预览入参。"""

    url: str = Field(description="要打开的完整 http(s) URL")
    title: str | None = Field(
        default=None,
        description="可选展示标题；省略则用页面 URL 主机名",
    )
    duration_s: float = Field(
        default=DEFAULT_DURATION_S,
        ge=2,
        le=30,
        description="停留并推送直播的秒数，默认 8",
    )

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        text = value.strip()
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url 必须是 http(s) 完整链接")
        return text


class PreviewOutput(BaseModel):
    """网页预览出参。"""

    ok: bool = True
    url: str
    title: str
    frames_sent: int = 0
    error_code: str | None = None
    message: str | None = None


def _default_title(url: str, override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    host = urlparse(url).netloc or url
    return f"预览 · {host}"


async def run_preview(inp: PreviewInput) -> PreviewOutput:
    """打开 URL，推送直播帧，返回摘要。"""
    title = _default_title(inp.url, inp.title)
    run_id = agent_run_id()
    frames_sent = 0

    async def on_frame(frame: dict[str, Any]) -> None:
        nonlocal frames_sent
        frames_sent += 1
        if run_id:
            await post_live_frame(run_id, frame)
        else:
            try:
                from src.cli.live import hub as live_hub

                live_hub.push_frame(
                    "orphan",
                    {
                        "type": "browserFrame",
                        "url": frame.get("url") or inp.url,
                        "title": frame.get("title") or title,
                        "hint": frame.get("hint"),
                        "mime": frame.get("mime") or "image/jpeg",
                        "image_b64": frame.get("image_b64") or "",
                    },
                )
            except Exception:  # noqa: BLE001
                pass

    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=True))
    page = None
    pump = None
    try:
        page = await port.open()
        ctx = CrawlContext(
            task_id=f"preview-{uuid.uuid4().hex[:10]}",
            meta={
                "live_frame_enabled": True,
                "on_live_frame": on_frame,
            },
        )
        logger.info("preview open url=%s run=%s duration=%s", inp.url, run_id or "-", inp.duration_s)
        await page.goto(inp.url, wait_until="domcontentloaded", timeout_ms=30_000)
        await emit_live_frame(ctx, page, title=title, hint="页面已打开")
        pump = await live_frame_pump(ctx, page, title=title, interval_s=1.0)
        await asyncio.sleep(float(inp.duration_s))
        final_url = page.url or inp.url
        await emit_live_frame(ctx, page, title=title, hint="预览结束")
        logger.info("preview done url=%s frames=%s", final_url, frames_sent)
        return PreviewOutput(ok=True, url=final_url, title=title, frames_sent=frames_sent)
    except AppError as exc:
        logger.warning("preview failed code=%s", exc.code)
        return PreviewOutput(
            ok=False,
            url=inp.url,
            title=title,
            frames_sent=frames_sent,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("preview failed")
        return PreviewOutput(
            ok=False,
            url=inp.url,
            title=title,
            frames_sent=frames_sent,
            error_code="tool.failed",
            message=str(exc)[:240],
        )
    finally:
        if pump is not None:
            await pump.aclose()
        if page is not None:
            await page.close()
        await manager.release(port)
