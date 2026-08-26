"""通用工具包 — web / browser / 渠道 / 知识。"""

from tools.alibaba import search_alibaba
from tools.browser import browser_available
from tools.knowledge import retrieve_knowledge
from tools.registry import (
    bind_skill_tools,
    format_tools_for_ai,
    list_skill_tools,
    list_tools,
    make_tools,
    tool_ai_schema,
    tools_for_skill,
)
from tools.web import (
    make_web_fetch_tool,
    make_web_research_tools,
    make_web_scrape_tool,
    scrape_url,
    search_hits,
    search_text,
)
from tools.xianyu import search_xianyu

__all__ = [
    "bind_skill_tools",
    "browser_available",
    "format_tools_for_ai",
    "list_skill_tools",
    "list_tools",
    "make_tools",
    "make_web_fetch_tool",
    "make_web_research_tools",
    "make_web_scrape_tool",
    "retrieve_knowledge",
    "scrape_url",
    "search_alibaba",
    "search_hits",
    "search_text",
    "search_xianyu",
    "tool_ai_schema",
    "tools_for_skill",
]
