"""Web LangChain 工具绑定 — web_fetch / web_scrape（实现见 tools.web.*）。"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dingda_sidecar.tools.web.fetch import clean_search_hits
from dingda_sidecar.tools.web.scrape import scrape_url
from dingda_sidecar.tools.web.search import search_hits

logger = logging.getLogger("dingda.tools.web.bindings")

_BODY_LIMIT = 2500


class WebFetchArgs(BaseModel):
    query: str = Field(description="搜索词；可按需加 site:example.com 限定站点")
    max_results: int = Field(default=5, ge=1, le=10, description="最多返回条数")


class WebScrapeArgs(BaseModel):
    url: str = Field(description="要抽取正文的完整 http(s) URL")


def _run_web_fetch(query: str, max_results: int = 5) -> str:
    q = (query or "").strip()
    if not q:
        return json.dumps({"ok": False, "error": "query 为空", "hits": []}, ensure_ascii=False)
    limit = max(1, min(int(max_results or 5), 10))
    raw = search_hits(q, max_results=limit)
    hits = clean_search_hits(raw, query=q)
    logger.info(
        "tool.web_fetch query=%s raw=%s cleaned=%s urls=%s",
        q[:120],
        len(raw),
        len(hits),
        [h.get("url") for h in hits if h.get("url")][:8],
    )
    return json.dumps({"ok": True, "query": q, "hits": hits}, ensure_ascii=False)


def _run_web_scrape(url: str) -> str:
    page = scrape_url(url, limit=_BODY_LIMIT)
    ok = bool(page.get("content") or page.get("url"))
    logger.info(
        "tool.web_scrape url=%s chars=%s",
        (page.get("url") or url)[:160],
        len(page.get("content") or ""),
    )
    return json.dumps({"ok": ok, **page}, ensure_ascii=False)


def make_web_fetch_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_run_web_fetch,
        name="web_fetch",
        description=(
            "检索公开网页，返回标题/链接/摘要列表。由你决定搜索词与是否使用 site:域名。"
            "需要正文时再对感兴趣的 URL 调用 web_scrape。"
        ),
        args_schema=WebFetchArgs,
    )


def make_web_scrape_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_run_web_scrape,
        name="web_scrape",
        description=(
            "对单个 URL 抓取并用 trafilatura 抽取正文。"
            "通常先 web_fetch 再对本工具传入具体链接；不要编造正文。"
        ),
        args_schema=WebScrapeArgs,
    )


def make_web_research_tools() -> list[StructuredTool]:
    return [make_web_fetch_tool(), make_web_scrape_tool()]


def sources_from_tool_payloads(payloads: list[str]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(item: dict[str, str]) -> None:
        key = item.get("url") or item.get("title") or ""
        if not key or key in seen:
            return
        seen.add(key)
        sources.append(item)

    for raw in payloads:
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue

        hits = data.get("hits")
        if isinstance(hits, list):
            query = str(data.get("query") or "")
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                _add(
                    {
                        "title": str(hit.get("title") or "")[:160],
                        "url": str(hit.get("url") or ""),
                        "snippet": str(hit.get("snippet") or "")[:400],
                        "content": str(hit.get("content") or "")[:_BODY_LIMIT],
                        "image": str(hit.get("image") or ""),
                        "query": str(hit.get("query") or query),
                    }
                )
            continue

        if data.get("url") or data.get("content"):
            content = str(data.get("content") or "")[:_BODY_LIMIT]
            _add(
                {
                    "title": str(data.get("title") or "")[:160],
                    "url": str(data.get("url") or ""),
                    "snippet": str(data.get("snippet") or content[:400])[:400],
                    "content": content,
                    "image": str(data.get("image") or ""),
                    "query": str(data.get("query") or ""),
                }
            )
    return sources


def format_web_context(sources: list[dict[str, str]], *, note: str = "") -> str:
    blocks: list[str] = []
    if note.strip():
        blocks.append(f"【调研助手备注】\n{note.strip()[:800]}")
    for i, src in enumerate(sources, 1):
        title = src.get("title") or "无标题"
        body = (src.get("content") or src.get("snippet") or "").strip()
        url = src.get("url") or ""
        query = src.get("query") or ""
        head = f"【材料{i}】{title}"
        if query:
            head += f"（检索：{query}）"
        if url:
            body = f"{body}\n来源：{url}".strip()
        blocks.append(f"{head}\n{body}".strip())
    return "\n\n".join(blocks)


__all__ = [
    "WebFetchArgs",
    "WebScrapeArgs",
    "format_web_context",
    "make_web_fetch_tool",
    "make_web_research_tools",
    "make_web_scrape_tool",
    "sources_from_tool_payloads",
]
