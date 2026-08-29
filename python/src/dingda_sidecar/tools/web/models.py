"""Web tool 共用模型。"""

from __future__ import annotations

from typing import TypedDict


class SearchHit(TypedDict, total=False):
    title: str
    url: str
    snippet: str
    image: str
    query: str


class PageContent(TypedDict, total=False):
    url: str
    title: str
    content: str
    snippet: str
