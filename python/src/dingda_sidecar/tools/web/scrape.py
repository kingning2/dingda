"""网页正文抽取 — trafilatura（先 fetch HTML 再抽主内容）。"""

from __future__ import annotations

import logging
import re

from dingda_sidecar.tools.web.fetch import clean_url, fetch_html
from dingda_sidecar.tools.web.models import PageContent

logger = logging.getLogger("dingda.tools.web.scrape")

_BODY_LIMIT = 2500


def extract_text(html: str, *, limit: int = _BODY_LIMIT) -> tuple[str, str]:
    """从 HTML 抽 (title, text)。"""
    if not html:
        return "", ""
    try:
        import trafilatura

        data = trafilatura.bare_extraction(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if data is None:
            text = (
                trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    favor_precision=True,
                )
                or ""
            )
            return "", re.sub(r"\s+", " ", text).strip()[:limit]

        if isinstance(data, dict):
            title = str(data.get("title") or "").strip()
            text = str(data.get("text") or data.get("raw_text") or "").strip()
        else:
            title = str(getattr(data, "title", "") or "").strip()
            text = str(getattr(data, "text", "") or getattr(data, "raw_text", "") or "").strip()
        return title[:160], re.sub(r"\s+", " ", text).strip()[:limit]
    except Exception as error:  # noqa: BLE001
        logger.warning("web.scrape.extract_failed err=%s", error)
        return "", ""


def scrape_url(url: str, *, limit: int = _BODY_LIMIT) -> PageContent:
    """抓取 URL 并抽正文。"""
    cleaned = clean_url(url)
    if not cleaned:
        return {"url": "", "title": "", "content": "", "snippet": ""}

    html = fetch_html(cleaned)
    title, text = extract_text(html, limit=limit)
    if text:
        logger.info("web.scrape.ok url=%s chars=%s", cleaned[:160], len(text))
    else:
        logger.warning("web.scrape.empty url=%s", cleaned[:160])
    return {
        "url": cleaned,
        "title": title,
        "content": text,
        "snippet": text[:400],
    }


def scrape_urls(
    urls: list[str],
    *,
    limit_each: int = _BODY_LIMIT,
    max_pages: int = 5,
) -> list[PageContent]:
    seen: set[str] = set()
    out: list[PageContent] = []
    for raw in urls:
        if len(out) >= max_pages:
            break
        page = scrape_url(raw, limit=limit_each)
        key = page.get("url") or ""
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(page)
    return out
