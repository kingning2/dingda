"""小红书搜索页 / 笔记详情：从 __INITIAL_STATE__ 抽成 CrawlItem。

职责：
    提供 SEARCH_JS / DETAIL_JS（页内 unwrap Vue ref）以及 Python 侧标准化。

设计说明：
    - 移植自 xhs_cli XhsClient.search_notes / get_note_detail，仅服务本 Source
    - 不含 Browser 启动或登录扫码
"""

from __future__ import annotations

import logging
from typing import Any

from src.crawler.core.types import CrawlItem

logger = logging.getLogger("dingda.crawler.xiaohongshu.extractor")

SEARCH_URL = "https://www.xiaohongshu.com/search_result"
NOTE_URL = "https://www.xiaohongshu.com/explore"

# Vue reactive 解包（与 xhs_cli client.UNWRAP_JS 对齐）
_UNWRAP_JS = r"""
function unwrap(obj, depth) {
    if (depth > 6 || obj === null || obj === undefined) return obj;
    if (typeof obj !== 'object') return obj;
    if ('_value' in obj && 'dep' in obj) return unwrap(obj._value, depth + 1);
    if ('value' in obj && 'dep' in obj) return unwrap(obj.value, depth + 1);
    if (Array.isArray(obj)) return obj.map(item => unwrap(item, depth + 1));
    const result = {};
    for (const key of Object.keys(obj)) {
        if (key === 'dep' || key.startsWith('__')) continue;
        try { result[key] = unwrap(obj[key], depth + 1); } catch(e) {}
    }
    return result;
}
""".strip()

SEARCH_READY_JS = r"""
() => {
  const s = window.__INITIAL_STATE__;
  if (!s || !s.search) return false;
  const f = s.search.feeds;
  if (!f) return false;
  const d = f._rawValue || f._value || f.value || f;
  return Array.isArray(d) || (d && typeof d === 'object');
}
"""

SEARCH_JS = (
    "() => {\n"
    + _UNWRAP_JS
    + r"""
  const s = window.__INITIAL_STATE__;
  if (!s || !s.search || !s.search.feeds) return { ready: false, items: [] };
  const feeds = unwrap(s.search.feeds, 0);
  const items = Array.isArray(feeds) ? feeds : [];
  return { ready: true, items };
}
"""
)

DETAIL_READY_JS = r"""
() => {
  const s = window.__INITIAL_STATE__;
  return !!(s && s.note && s.note.noteDetailMap
    && Object.keys(s.note.noteDetailMap).length > 0);
}
"""

DETAIL_JS = (
    "(noteId) => {\n"
    + _UNWRAP_JS
    + r"""
  const s = window.__INITIAL_STATE__;
  if (!s || !s.note || !s.note.noteDetailMap) return { ready: false, note: null };
  const map = unwrap(s.note.noteDetailMap, 0) || {};
  const note = map[noteId] || map[Object.keys(map)[0]] || null;
  return { ready: !!note, note };
}
"""
)


def _card(row: dict[str, Any]) -> dict[str, Any]:
    card = row.get("noteCard") or row.get("note_card") or row.get("note") or {}
    return card if isinstance(card, dict) else {}


def _note_id(row: dict[str, Any]) -> str:
    card = _card(row)
    for key in ("id", "note_id", "noteId"):
        value = row.get(key) or card.get(key)
        if value:
            return str(value)
    return ""


def _title(row: dict[str, Any]) -> str:
    card = _card(row)
    for key in ("display_title", "displayTitle", "title"):
        value = row.get(key) or card.get(key)
        if value:
            return str(value).strip()
    return ""


def _seller(row: dict[str, Any]) -> str:
    card = _card(row)
    user = row.get("user") or card.get("user") or {}
    if not isinstance(user, dict):
        return ""
    return str(user.get("nickname") or user.get("nickName") or "")


def _xsec_token(row: dict[str, Any]) -> str:
    card = _card(row)
    for key in ("xsecToken", "xsec_token"):
        value = row.get(key) or card.get(key)
        if value:
            return str(value)
    return ""


def _cover(row: dict[str, Any]) -> str:
    card = _card(row)
    cover = row.get("cover") or card.get("cover") or {}
    if isinstance(cover, str):
        return cover
    if not isinstance(cover, dict):
        return ""
    url = cover.get("url") or cover.get("infoList")
    if isinstance(url, str):
        return url
    if isinstance(url, list) and url:
        first = url[0]
        if isinstance(first, dict):
            return str(first.get("url") or "")
        return str(first)
    return ""


def items_from_feeds(payload: dict[str, Any] | list[Any], *, limit: int) -> list[CrawlItem]:
    """搜索 feeds → CrawlItem 列表。"""
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("items")
        rows = raw_items if isinstance(raw_items, list) else []
    else:
        return []
    out: list[CrawlItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        note_id = _note_id(row)
        title = _title(row)
        if not note_id or not title:
            continue
        out.append(
            CrawlItem(
                item_id=note_id,
                title=title,
                url=f"{NOTE_URL}/{note_id}",
                price=None,
                raw={
                    "seller_nick": _seller(row),
                    "xsec_token": _xsec_token(row),
                    "image_url": _cover(row),
                    "feed": row,
                },
            )
        )
        if len(out) >= limit:
            break
    return out


def item_from_detail(payload: dict[str, Any], note_id: str) -> CrawlItem:
    """noteDetailMap 一条 → CrawlItem。"""
    blob = payload.get("note") if isinstance(payload.get("note"), dict) else payload
    inner = blob.get("note") if isinstance(blob.get("note"), dict) else blob
    if not isinstance(inner, dict):
        inner = {}
    resolved_id = str(inner.get("noteId") or inner.get("id") or note_id)
    title = str(inner.get("title") or inner.get("displayTitle") or "").strip()
    user = inner.get("user") if isinstance(inner.get("user"), dict) else {}
    nick = str(user.get("nickname") or user.get("nickName") or "")
    token = str(inner.get("xsecToken") or inner.get("xsec_token") or "")
    return CrawlItem(
        item_id=resolved_id,
        title=title,
        url=f"{NOTE_URL}/{resolved_id}",
        price=None,
        raw={"seller_nick": nick, "xsec_token": token, "note": blob},
    )
