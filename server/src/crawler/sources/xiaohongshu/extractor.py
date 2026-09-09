"""小红书搜索页 / 笔记详情：从 XHR / DOM / __INITIAL_STATE__ 抽成 CrawlItem。

职责：
    提供 SEARCH_JS / DOM_SEARCH_JS / DETAIL_JS 以及 Python 侧标准化。

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

# 现网常无 __INITIAL_STATE__：从结果卡 DOM 抽 note id / 标题
DOM_SEARCH_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const nodes = document.querySelectorAll(
    'a[href*="/explore/"], a[href*="/search_result/"]'
  );
  for (const a of nodes) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/\/(?:explore|search_result)\/([0-9a-f]{24})/i);
    if (!m) continue;
    const id = m[1];
    if (seen.has(id)) continue;
    const card = a.closest('section, .note-item, [class*="note"]') || a.parentElement;
    let title = '';
    const titleEl = card && card.querySelector(
      '.title, .footer .title, a.title, [class*="title"]'
    );
    if (titleEl) title = (titleEl.textContent || '').trim();
    if (!title) {
      title = (a.getAttribute('title') || a.getAttribute('aria-label') || '').trim();
    }
    if (!title) continue;
    const img = a.querySelector('img');
    seen.add(id);
    out.push({
      id,
      noteCard: {
        displayTitle: title,
        cover: { url: (img && img.src) || '' },
      },
    });
  }
  return { items: out };
}
"""

# 诊断：是否登录墙 / 有没有结果卡 / 还有没有 INITIAL_STATE
PAGE_HINT_JS = r"""
() => {
  const text = ((document.body && document.body.innerText) || '').slice(0, 2500);
  const login = /登录后|扫码登录|手机号登录|请先登录|打开小红书App/.test(text)
    || !!document.querySelector(
      '.login-container, .qrcode-img, [class*="login-box"], [class*="login-modal"]'
    );
  return {
    url: location.href || '',
    title: document.title || '',
    login,
    noteLinkCount: document.querySelectorAll('a[href*="/explore/"]').length,
    hasInitial: !!(window.__INITIAL_STATE__ && window.__INITIAL_STATE__.search),
  };
}
"""

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

# 现网详情是搜索页上的弹层卡片，不是独立 SSR 页；从弹层 DOM 抽标题/作者
DOM_DETAIL_JS = r"""
(noteId) => {
  const href = location.href || '';
  if (/error_code=300031|\/404\?/.test(href)) {
    return { ready: false, blocked: true, note: null };
  }
  const idFromUrl = (href.match(/\/explore\/([0-9a-f]{24})/i) || [])[1] || noteId || '';

  const authorEl = document.querySelector(
    '.author-container .username, .author-wrapper .username, .author-wrapper .name, a.name .username, [class*="author"] .username'
  );
  const nick = authorEl ? (authorEl.textContent || '').trim() : '';

  let title = '';
  const titleEl = document.querySelector(
    '#detail-title, .note-content .title, .interaction-content .title, [class*="note-content"] [class*="title"]'
  );
  if (titleEl) title = (titleEl.textContent || '').trim();
  if (!title) {
    title = (document.title || '').replace(/\s*[-–|]\s*小红书\s*$/u, '').trim();
  }
  if (!title || /你访问的页面不存在|小红书$/.test(title)) {
    return { ready: false, blocked: false, note: null };
  }

  // 弹层已出现：作者区或互动条任一存在即可
  const hasCard = !!(
    authorEl
    || document.querySelector('.interactions-footer, .engage-bar, .note-detail-mask, #noteContainer, .note-container')
  );
  if (!hasCard && !/\/explore\//.test(href)) {
    return { ready: false, blocked: false, note: null };
  }

  return {
    ready: true,
    blocked: false,
    note: {
      noteId: idFromUrl,
      title,
      user: { nickname: nick },
    },
  };
}
"""

DETAIL_HINT_JS = r"""
() => {
  const params = new URLSearchParams(location.search || '');
  return {
    url: location.href || '',
    title: document.title || '',
    error_code: params.get('error_code') || '',
    error_msg: params.get('error_msg') || '',
    hasCard: !!document.querySelector(
      '#noteContainer, .note-container, .author-container, .interactions-footer, .engage-bar'
    ),
  };
}
"""


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


def _note_image_urls(note: dict[str, Any]) -> list[str]:
    """从笔记详情结构抽出图片 URL（封面 + image_list）。"""
    out: list[str] = []
    seen: set[str] = set()

    def _add(url: Any) -> None:
        text = str(url or "").strip()
        if not text.startswith("http") or text in seen:
            return
        seen.add(text)
        out.append(text)

    cover = note.get("cover")
    if isinstance(cover, str):
        _add(cover)
    elif isinstance(cover, dict):
        _add(cover.get("url"))
        info = cover.get("infoList") or cover.get("url_default")
        if isinstance(info, list):
            for row in info:
                if isinstance(row, dict):
                    _add(row.get("url"))
                else:
                    _add(row)

    for key in ("image_list", "imageList", "images"):
        blob = note.get(key)
        if not isinstance(blob, list):
            continue
        for row in blob:
            if isinstance(row, str):
                _add(row)
                continue
            if not isinstance(row, dict):
                continue
            _add(row.get("url") or row.get("url_default"))
            info = row.get("info_list") or row.get("infoList")
            if isinstance(info, list) and info:
                first = info[0]
                if isinstance(first, dict):
                    _add(first.get("url"))

    return out


def _note_desc(note: dict[str, Any]) -> str:
    """笔记正文描述。"""
    for key in ("desc", "description", "content"):
        value = note.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
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
    """详情弹层 / noteDetailMap / feed 一条 → CrawlItem。"""
    blob = payload.get("note") if isinstance(payload.get("note"), dict) else payload
    # feed: { items: [{ note_card / noteCard }] }
    if isinstance(blob, dict) and not blob.get("title") and not blob.get("noteId"):
        items = blob.get("items")
        if isinstance(items, list) and items:
            first = items[0] if isinstance(items[0], dict) else {}
            card = first.get("note_card") or first.get("noteCard") or first
            if isinstance(card, dict):
                blob = card
    inner = blob.get("note") if isinstance(blob.get("note"), dict) else blob
    if not isinstance(inner, dict):
        inner = {}
    resolved_id = str(
        inner.get("noteId") or inner.get("note_id") or inner.get("id") or note_id
    )
    title = str(
        inner.get("title")
        or inner.get("displayTitle")
        or inner.get("display_title")
        or ""
    ).strip()
    user = inner.get("user") if isinstance(inner.get("user"), dict) else {}
    nick = str(user.get("nickname") or user.get("nickName") or "")
    token = str(inner.get("xsecToken") or inner.get("xsec_token") or "")
    interact = inner.get("interact_info") or inner.get("interactInfo") or {}
    liked = ""
    collected = ""
    if isinstance(interact, dict):
        liked = str(interact.get("liked_count") or interact.get("likedCount") or "")
        collected = str(
            interact.get("collected_count") or interact.get("collectedCount") or ""
        )
    image_urls = _note_image_urls(inner)
    desc = _note_desc(inner)
    cover = image_urls[0] if image_urls else ""
    return CrawlItem(
        item_id=resolved_id,
        title=title,
        url=f"{NOTE_URL}/{resolved_id}",
        price=None,
        raw={
            "seller_nick": nick,
            "xsec_token": token,
            "want_count": collected or None,
            "browse_count": liked or None,
            "image_url": cover or None,
            "image_urls": image_urls,
            "desc": desc or None,
            "note": blob,
        },
    )
