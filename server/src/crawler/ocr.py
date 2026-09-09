"""图片 OCR（选品图文识字）。

职责：
    把图片 bytes / URL 识别成纯文本，供小红书笔记等图文提取。
    Crawler Source 在详情里调用；失败时返回空串，不打断抓取。

设计说明：
    - 优先 RapidOCR（onnx）；未安装或推理失败则透传空结果
    - 不依赖系统 Tesseract 安装
    - 引擎懒加载；Agent 开跑时后台 ``warm_ocr``（与思考并行），不在 Server 启动时预热

使用示例：
    warm_ocr()  # 后台调用即可
    text = ocr_image_bytes(jpeg_bytes)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger("dingda.crawler.ocr")

_MAX_CHARS = 2400


@lru_cache(maxsize=1)
def _engine() -> Any | None:
    """懒加载 RapidOCR；未安装返回 None。"""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        logger.warning("rapidocr-onnxruntime 未安装，OCR 不可用")
        return None
    try:
        return RapidOCR()
    except Exception:  # noqa: BLE001
        logger.exception("RapidOCR 初始化失败")
        return None


def warm_ocr() -> bool:
    """幂等预热 RapidOCR（Agent 开跑时后台调用；已热则瞬间返回）。"""
    ready = _engine() is not None
    logger.info("ocr warm ready=%s", ready)
    return ready


def ocr_image_bytes(data: bytes) -> str:
    """对图片字节做 OCR，返回合并文本。"""
    if not data:
        return ""
    engine = _engine()
    if engine is None:
        return ""
    try:
        result, _ = engine(data)
    except Exception:  # noqa: BLE001
        logger.debug("ocr_image_bytes failed", exc_info=True)
        return ""
    if not result:
        return ""
    lines: list[str] = []
    for row in result:
        if not row or len(row) < 2:
            continue
        text = str(row[1] or "").strip()
        if text:
            lines.append(text)
    joined = "\n".join(lines).strip()
    if len(joined) > _MAX_CHARS:
        return joined[:_MAX_CHARS].rstrip() + "…"
    return joined


def ocr_image_url(url: str, *, referer: str | None = None) -> str:
    """下载图片再 OCR；失败返回空串。"""
    text_url = (url or "").strip()
    if not text_url.startswith("http"):
        return ""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx 未安装，无法下载图片做 OCR")
        return ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": (referer or "https://www.xiaohongshu.com/").strip(),
    }
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(text_url, headers=headers)
            if resp.status_code >= 400:
                logger.debug("ocr download failed status=%s", resp.status_code)
                return ""
            return ocr_image_bytes(resp.content)
    except Exception:  # noqa: BLE001
        logger.debug("ocr_image_url failed url=%s", text_url[:80], exc_info=True)
        return ""


def ocr_image_urls(
    urls: list[str],
    *,
    referer: str | None = None,
    max_images: int = 3,
) -> str:
    """多图 OCR，按顺序合并；最多 max_images 张。"""
    parts: list[str] = []
    for url in urls[: max(0, max_images)]:
        text = ocr_image_url(url, referer=referer)
        if text:
            parts.append(text)
    return "\n---\n".join(parts).strip()
