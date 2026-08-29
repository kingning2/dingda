"""网页检索 — DuckDuckGo HTML 命中；Instant Answer 兜底。只返回链接摘要，不抽正文。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from dingda_sidecar.tools.web.models import SearchHit

logger = logging.getLogger("dingda.tools.web.search")

_DDG_BASE = "https://duckduckgo.com"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _abs_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        return urljoin(_DDG_BASE, value)
    return value


def _unwrap_ddg_redirect(href: str) -> str:
    url = _abs_url(href)
    if "uddg=" not in url:
        return url
    try:
        query = parse_qs(urlparse(url).query)
        target = (query.get("uddg") or [""])[0]
        return unquote(target) if target else url
    except Exception:  # noqa: BLE001
        return url


def _walk_topics(items: list[Any], hits: list[dict[str, str]], *, limit: int) -> None:
    for item in items:
        if len(hits) >= limit:
            return
        if not isinstance(item, dict):
            continue
        nested = item.get("Topics")
        if isinstance(nested, list):
            _walk_topics(nested, hits, limit=limit)
            continue
        text = str(item.get("Text") or "").strip()
        url = _abs_url(str(item.get("FirstURL") or ""))
        icon = item.get("Icon") if isinstance(item.get("Icon"), dict) else {}
        image = _abs_url(str((icon or {}).get("URL") or ""))
        if not (text or url):
            continue
        title = text.split(" - ", 1)[0].strip() if text else url
        hits.append(
            {
                "title": title[:120],
                "url": url,
                "snippet": text[:400],
                "image": image,
            }
        )


def _dedupe(hits: list[dict[str, str]], *, limit: int) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for hit in hits:
        key = hit.get("url") or hit.get("title") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(hit)
        if len(unique) >= limit:
            break
    return unique


def _ddg_instant_hits(query: str, *, max_results: int) -> list[dict[str, str]]:
    params = urlencode(
        {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
        },
    )
    url = f"https://api.duckduckgo.com/?{params}"
    req = Request(url, headers={"User-Agent": _UA})
    with urlopen(req, timeout=15) as response:  # noqa: S310
        data = json.loads(response.read().decode("utf-8"))

    hits: list[dict[str, str]] = []
    abstract = str(data.get("AbstractText") or "").strip()
    abstract_url = _abs_url(str(data.get("AbstractURL") or ""))
    heading = str(data.get("Heading") or "").strip() or query
    image = _abs_url(str(data.get("Image") or ""))
    if abstract or abstract_url:
        hits.append(
            {
                "title": heading[:120],
                "url": abstract_url,
                "snippet": abstract[:400],
                "image": image,
            }
        )
    related = data.get("RelatedTopics") or []
    if isinstance(related, list):
        _walk_topics(related, hits, limit=max_results)
    return _dedupe(hits, limit=max_results)


_RESULT_BLOCK_RE = re.compile(
    r'class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|td|div)>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", raw)).strip()


def _ddg_html_hits(query: str, *, max_results: int) -> list[dict[str, str]]:
    params = urlencode({"q": query})
    url = f"https://html.duckduckgo.com/html/?{params}"
    req = Request(url, headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    with urlopen(req, timeout=20) as response:  # noqa: S310
        html = response.read().decode("utf-8", errors="ignore")

    anchors = list(_RESULT_BLOCK_RE.finditer(html))
    snippets = [_strip_html(m.group(1)) for m in _SNIPPET_RE.finditer(html)]
    hits: list[dict[str, str]] = []
    for index, match in enumerate(anchors):
        if len(hits) >= max_results:
            break
        href = _unwrap_ddg_redirect(match.group(1))
        title = _strip_html(match.group(2))
        if not href or not title:
            continue
        if "duckduckgo.com" in href and "uddg=" not in href:
            continue
        snippet = snippets[index] if index < len(snippets) else ""
        hits.append(
            {
                "title": title[:160],
                "url": href,
                "snippet": snippet[:400],
                "image": "",
            }
        )
    return _dedupe(hits, limit=max_results)


def search_hits(query: str, *, max_results: int = 8) -> list[SearchHit]:
    """结构化检索命中：title / url / snippet / image。"""
    q = query.strip()
    if not q:
        return []

    hits: list[dict[str, str]] = []
    source = "none"
    try:
        hits = _ddg_html_hits(q, max_results=max_results)
        source = "html"
    except Exception as error:  # noqa: BLE001
        logger.warning("web.search.html.failed query=%s err=%s", q[:80], error)

    if not hits:
        try:
            hits = _ddg_instant_hits(q, max_results=max_results)
            source = "instant"
        except Exception as error:  # noqa: BLE001
            logger.warning("web.search.instant.failed query=%s err=%s", q[:80], error)
            hits = []

    urls = [h.get("url") or "" for h in hits if h.get("url")]
    logger.info(
        "web.search done query=%s source=%s hits=%s urls=%s",
        q[:120],
        source,
        len(hits),
        urls[:8],
    )
    return hits  # type: ignore[return-value]


def search_text(query: str, *, max_results: int = 5) -> str:
    """纯文本摘要。"""
    hits = search_hits(query, max_results=max_results)
    parts: list[str] = []
    for hit in hits:
        title = hit.get("title") or ""
        snippet = hit.get("snippet") or ""
        url = hit.get("url") or ""
        line = snippet or title
        if url:
            line = f"{line}\n{url}".strip()
        if line:
            parts.append(line)
    return "\n\n".join(parts)


# 兼容旧名
web_fetch_hits = search_hits
web_fetch = search_text
