"""网页搜索 — DuckDuckGo Instant Answer。

无密钥 HTTP 查询，为 Graph search 节点提供轻量外网摘要。"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen


def web_search(query: str, *, max_results: int = 5) -> str:
    q = query.strip()
    if not q:
        return ""
    params = urlencode(
        {
            "q": q,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
        },
    )
    url = f"https://api.duckduckgo.com/?{params}"
    with urlopen(url, timeout=15) as response:  # noqa: S310
        data = json.loads(response.read().decode("utf-8"))

    parts: list[str] = []
    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        parts.append(abstract)
    count = 0
    for item in data.get("RelatedTopics") or []:
        if count >= max_results:
            break
        text = item.get("Text") if isinstance(item, dict) else None
        if text:
            parts.append(str(text).strip())
            count += 1
    return "\n".join(parts)
