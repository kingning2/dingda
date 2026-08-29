"""tools.web — search / fetch / scrape / LangChain bindings。"""

from dingda_sidecar.tools.web.bindings import (
    format_web_context,
    make_web_fetch_tool,
    make_web_research_tools,
    make_web_scrape_tool,
    sources_from_tool_payloads,
)
from dingda_sidecar.tools.web.fetch import clean_search_hits, clean_url, fetch_html
from dingda_sidecar.tools.web.scrape import scrape_url, scrape_urls
from dingda_sidecar.tools.web.search import search_hits, search_text

__all__ = [
    "clean_search_hits",
    "clean_url",
    "fetch_html",
    "format_web_context",
    "make_web_fetch_tool",
    "make_web_research_tools",
    "make_web_scrape_tool",
    "scrape_url",
    "scrape_urls",
    "search_hits",
    "search_text",
    "sources_from_tool_payloads",
]
