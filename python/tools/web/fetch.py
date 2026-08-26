"""网页抓取 — 下载原始 HTML（清洗 URL 后）。"""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

logger = logging.getLogger("dingda.tools.web.fetch")

_TRACKING_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "spm",
        "scm",
        "fbclid",
        "gclid",
        "msclkid",
    }
)
_BLOCKED_HOST_PARTS = ("duckduckgo.com", "google.com/search", "bing.com/search")


def clean_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        return ""
    lower = url.lower()
    if any(part in lower for part in _BLOCKED_HOST_PARTS):
        return ""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ""
        query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_KEYS
        ]
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",
                urlencode(query, doseq=True),
                "",
            )
        )
    except Exception:  # noqa: BLE001
        return url.split("#", 1)[0].strip()


def fetch_html(url: str) -> str:
    """下载页面 HTML；失败返回空串。"""
    cleaned = clean_url(url)
    if not cleaned:
        return ""
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(cleaned)
        html = downloaded or ""
        logger.info("web.fetch url=%s bytes=%s", cleaned[:160], len(html))
        return html
    except Exception as error:  # noqa: BLE001
        logger.warning("web.fetch.failed url=%s err=%s", cleaned[:160], error)
        return ""


def clean_search_hits(hits: list[dict[str, str]], *, query: str = "") -> list[dict[str, str]]:
    """清洗检索命中（去引擎页 / 跟踪参数 / 去重）。"""
    seen: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for hit in hits:
        title = re.sub(r"\s+", " ", str(hit.get("title") or "")).strip()[:160]
        snippet = re.sub(r"\s+", " ", str(hit.get("snippet") or "")).strip()[:400]
        url = clean_url(str(hit.get("url") or ""))
        image = str(hit.get("image") or "").strip()
        if image.startswith("//"):
            image = f"https:{image}"
        if not (title or snippet or url):
            continue
        key = url or title
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "image": image,
                "query": query,
            }
        )
    return cleaned
