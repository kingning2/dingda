"""小红书搜索页 / 笔记详情：从 XHR / DOM / __INITIAL_STATE__ 抽成 CrawlItem。

职责：
    提供 SEARCH_JS / DOM_SEARCH_JS / DETAIL_JS 以及 Python 侧标准化。
    DOM 选择器、API 匹配串、列表/详情/评论字段路径一律来自同目录 ``extract.json``。

设计说明：
    - 移植自 xhs_cli XhsClient.search_notes / get_note_detail，仅服务本 Source
    - evaluate 脚本通过 ``*_arg()`` 或模块加载时嵌入 JSON 注入配置，JS 内不写死选择器
    - 不含 Browser 启动或登录扫码
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping

from crawler.core.types import CrawlItem
from crawler.extraction.config import (
    dig_first,
    dig_str,
    load_extract_json,
    path_list,
    section,
)

logger = logging.getLogger("dingda.crawler.xiaohongshu.extractor")

EXTRACT = load_extract_json(__file__)
_URLS = section(EXTRACT, "urls")
SEARCH_URL = str(_URLS.get("search") or "")
NOTE_URL = str(_URLS.get("note") or "")


def _sec(name: str) -> dict[str, Any]:
    """读最新缓存中的小节（写回 extract.json 后立即生效）。"""
    return section(load_extract_json(__file__), name)


def _fields(api: dict[str, Any]) -> dict[str, Any]:
    fields = api.get("fields")
    return fields if isinstance(fields, dict) else {}


def _js(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def search_dom_arg() -> dict[str, Any]:
    """``page.evaluate(DOM_SEARCH_JS, …)``：注入 extract.json 的 dom。"""
    return {"dom": _sec("dom")}


def page_hint_arg() -> dict[str, Any]:
    """``PAGE_HINT_JS`` 参数：登录文案、登录 DOM 与 note 链接计数选择器。"""
    return {"signals": _sec("signals"), "dom": _sec("dom")}


def detail_dom_arg(note_id: str) -> dict[str, Any]:
    """``page.evaluate(DOM_DETAIL_JS, …)``：noteId + detail_dom。"""
    return {"noteId": str(note_id), "dom": _sec("detail_dom")}


def detail_hint_arg() -> dict[str, Any]:
    """``DETAIL_HINT_JS`` 参数：detail_hint_dom。"""
    return {"dom": _sec("detail_hint_dom")}


def comments_dom_arg() -> dict[str, Any]:
    """``SCROLL_COMMENTS_JS`` / ``DOM_COMMENTS_JS`` 参数：comments_dom。"""
    return {"dom": _sec("comments_dom")}


def state_arg() -> dict[str, Any]:
    """``SEARCH_JS`` / ``DETAIL_JS`` 等页内 state 路径（``__INITIAL_STATE__``）。"""
    return {"state": _sec("state")}


def list_api_match_urls() -> tuple[str, ...]:
    """搜索列表 XHR URL 子串（截获用）。"""
    return tuple(path_list(_sec("list_api"), "match_urls"))


def feed_api_match_urls() -> tuple[str, ...]:
    """详情 feed XHR URL 子串（截获用）。"""
    return tuple(path_list(_sec("detail_api"), "match_urls"))


def comment_api_matchers() -> dict[str, list[str]]:
    """comment/page URL 匹配：contains / excludes 列表。"""
    cfg = _sec("comment_api")
    return {
        "contains": path_list(cfg, "match_contains"),
        "excludes": path_list(cfg, "match_excludes"),
    }


def capture_url_hints() -> tuple[str, ...]:
    """诊断日志：edith / api/sns 等 URL 提示。"""
    return tuple(path_list(_sec("capture"), "url_hints"))


def cookie_domain() -> str:
    """浏览器 cookie 域名。"""
    return str(_URLS.get("cookie_domain") or "")


def ocr_referer() -> str:
    """OCR 请求 Referer。"""
    return str(_URLS.get("ocr_referer") or _URLS.get("note") or "")


def search_goto_params(query: str) -> dict[str, Any]:
    """搜索页 goto query 参数（keyword + static）。"""
    cfg = _sec("search_params")
    data = dict(cfg.get("static") if isinstance(cfg.get("static"), dict) else {})
    key = str(cfg.get("keyword_key") or "")
    if key:
        data[key] = query
    return data


def behavior_meta() -> dict[str, Any]:
    """轮询 / 滚动 / 匿名作者等行为常量。"""
    return _sec("behavior")


def limits_meta() -> dict[str, int]:
    """默认 / 上限条数。"""
    cfg = _sec("limits")
    return {
        "default_limit": int(cfg["default_limit"]) if isinstance(cfg.get("default_limit"), int) else 20,
        "max_limit": int(cfg["max_limit"]) if isinstance(cfg.get("max_limit"), int) else 100,
    }


def note_error_codes() -> tuple[str, ...]:
    """详情不可浏览错误码。"""
    return tuple(path_list(_sec("signals"), "note_error_codes"))


def capture_http_methods() -> tuple[str, ...]:
    """截获允许的 HTTP method。"""
    return tuple(path_list(_sec("capture"), "http_methods"))


def detail_goto_params(*, token: str, source: str | None = None) -> dict[str, str]:
    """详情页 goto 参数（xsec_token / xsec_source）。"""
    cfg = _sec("detail_params")
    token_key = str(cfg.get("xsec_token_key") or "")
    source_key = str(cfg.get("xsec_source_key") or "")
    default_source = str(cfg.get("default_xsec_source") or "")
    out: dict[str, str] = {}
    if token_key and token:
        out[token_key] = token
    if source_key:
        out[source_key] = (source or default_source).strip() or default_source
    return out


def normalized_video_type() -> str:
    """列表/详情归一化后的视频类型标记。"""
    return str(_sec("list_api").get("normalized_video") or "")


def url_block_rules() -> dict[str, list[str]]:
    """风控 / 登录墙 / 笔记不可浏览 URL 子串。"""
    signals = _sec("signals")
    return {
        "blocked_url": path_list(signals, "blocked_url"),
        "login_url": path_list(signals, "login_url"),
        "note_blocked_url": path_list(signals, "note_blocked_url"),
    }


# Vue / state / DOM 脚本：特例全部来自 extract.json
_STATE = _sec("state")
_BEHAVIOR = _sec("behavior")
_GLOBAL_NAME = str(_STATE.get("global_name") or "")
_SEARCH_FEEDS_PATH = str(_STATE.get("search_feeds") or "")
_NOTE_DETAIL_MAP_PATH = str(_STATE.get("note_detail_map") or "")
_SEARCH_STATE_ROOT = _SEARCH_FEEDS_PATH.split(".", 1)[0] if _SEARCH_FEEDS_PATH else ""
_UNWRAP_RAW_KEYS = path_list(_STATE, "unwrap_raw_keys")
_UNWRAP_SKIP_KEYS = path_list(_STATE, "unwrap_skip_keys")
_UNWRAP_SKIP_PREFIX = str(_STATE.get("unwrap_skip_prefix") or "")
_UNWRAP_MAX_DEPTH = int(_STATE["unwrap_max_depth"]) if isinstance(_STATE.get("unwrap_max_depth"), int) else 6
_BODY_PREVIEW = int(_BEHAVIOR["body_preview_chars"]) if isinstance(_BEHAVIOR.get("body_preview_chars"), int) else 2500
_DETAIL_DOM_JSON = _js(_sec("detail_dom"))
_COMMENTS_DOM_JSON = _js(_sec("comments_dom"))
_DOM_JSON = _js(_sec("dom"))

_UNWRAP_JS = f"""
function unwrap(obj, depth) {{
  const maxDepth = {_UNWRAP_MAX_DEPTH};
  const rawKeys = {_js(_UNWRAP_RAW_KEYS)};
  const skipKeys = {_js(_UNWRAP_SKIP_KEYS)};
  const skipPrefix = {_js(_UNWRAP_SKIP_PREFIX)};
  if (depth > maxDepth || obj === null || obj === undefined) return obj;
  if (typeof obj !== 'object') return obj;
  for (const k of rawKeys) {{
    if (k in obj && skipKeys.some((s) => s in obj)) return unwrap(obj[k], depth + 1);
  }}
  if (Array.isArray(obj)) return obj.map(item => unwrap(item, depth + 1));
  const result = {{}};
  for (const key of Object.keys(obj)) {{
    if (skipKeys.includes(key) || (skipPrefix && key.startsWith(skipPrefix))) continue;
    try {{ result[key] = unwrap(obj[key], depth + 1); }} catch(e) {{}}
  }}
  return result;
}}
""".strip()

_DIG_STATE_JS = r"""
function digState(obj, path) {
  if (!path) return undefined;
  const parts = String(path).split('.');
  let cur = obj;
  for (let i = 0; i < parts.length; i++) {
    if (cur === null || cur === undefined || typeof cur !== 'object') return undefined;
    cur = cur[parts[i]];
  }
  return cur;
}
""".strip()

_PICK_RAW_JS = f"""
function pickRaw(wrap) {{
  if (!wrap) return wrap;
  const keys = {_js(_UNWRAP_RAW_KEYS)};
  for (const k of keys) {{
    if (wrap[k] !== undefined) return wrap[k];
  }}
  return wrap;
}}
""".strip()

SEARCH_READY_JS = (
    "() => {\n"
    + _DIG_STATE_JS
    + "\n"
    + _PICK_RAW_JS
    + f"""
  const s = window[{_js(_GLOBAL_NAME)}];
  if (!s) return false;
  const f = digState(s, {_js(_SEARCH_FEEDS_PATH)});
  if (!f) return false;
  const d = pickRaw(f);
  return Array.isArray(d) || (d && typeof d === 'object');
}}
"""
)

SEARCH_JS = (
    "(opts) => {\n"
    + _UNWRAP_JS
    + "\n"
    + _DIG_STATE_JS
    + f"""
  const statePath = (opts && opts.state && opts.state.search_feeds) || {_js(_SEARCH_FEEDS_PATH)};
  const s = window[{_js(_GLOBAL_NAME)}];
  const feedsWrap = s ? digState(s, statePath) : undefined;
  if (!feedsWrap) return {{ ready: false, items: [] }};
  const feeds = unwrap(feedsWrap, 0);
  const items = Array.isArray(feeds) ? feeds : [];
  return {{ ready: true, items }};
}}
"""
)

DOM_SEARCH_JS = (
    "(opts) => {\n"
    + f"""
  const dom = (opts && opts.dom) || {_DOM_JSON};
  if (!dom) return {{ items: [] }};
  const out = [];
  const seen = new Set();
  const linkSel = dom.links;
  const idRe = new RegExp(dom.id_pattern, 'i');
  const cardSel = dom.card;
  const titleSel = dom.title;
  const imgSel = dom.img;
  const titleAttrs = dom.title_attrs || [];
  const cardOut = dom.card_output || {{}};
  const nodes = document.querySelectorAll(linkSel);
  for (const a of nodes) {{
    const href = a.getAttribute('href') || '';
    const m = href.match(idRe);
    if (!m) continue;
    const id = m[1];
    if (seen.has(id)) continue;
    const card = a.closest(cardSel) || a.parentElement;
    let title = '';
    const titleEl = card && card.querySelector(titleSel);
    if (titleEl) title = (titleEl.textContent || '').trim();
    if (!title) {{
      for (const attr of titleAttrs) {{
        title = (a.getAttribute(attr) || '').trim();
        if (title) break;
      }}
    }}
    if (!title) continue;
    const img = imgSel ? a.querySelector(imgSel) : null;
    seen.add(id);
    const coverKeys = cardOut.cover_url_keys || [];
    let coverObj = (img && img.src) || '';
    if (coverKeys.length >= 2) {{
      coverObj = {{ [coverKeys[0]]: {{ [coverKeys[1]]: (img && img.src) || '' }} }};
    }} else if (coverKeys.length === 1) {{
      coverObj = {{ [coverKeys[0]]: (img && img.src) || '' }};
    }}
    const row = {{}};
    row[cardOut.id_key || 'id'] = id;
    if (cardOut.card_key) {{
      const noteCard = {{}};
      noteCard[cardOut.title_key || 'displayTitle'] = title;
      if (coverKeys.length >= 2) {{
        noteCard[coverKeys[0]] = {{ [coverKeys[1]]: (img && img.src) || '' }};
      }}
      row[cardOut.card_key] = noteCard;
    }}
    out.push(row);
  }}
  return {{ items: out }};
}}
"""
)

PAGE_HINT_JS = (
    "(opts) => {\n"
    + _DIG_STATE_JS
    + f"""
  const signals = (opts && opts.signals) || {{}};
  const dom = (opts && opts.dom) || {{}};
  const preview = {_BODY_PREVIEW};
  const text = ((document.body && document.body.innerText) || '').slice(0, preview);
  const loginKeys = signals.login || [];
  const login = loginKeys.some((k) => text.includes(k))
    || !!(signals.login_dom && document.querySelector(signals.login_dom));
  const stateRoot = {_js(_SEARCH_STATE_ROOT)};
  const globalName = {_js(_GLOBAL_NAME)};
  return {{
    url: location.href || '',
    title: document.title || '',
    login,
    noteLinkCount: dom.note_link_count
      ? document.querySelectorAll(dom.note_link_count).length
      : 0,
    hasInitial: !!(window[globalName] && digState(window[globalName], stateRoot)),
  }};
}}
"""
)

DETAIL_READY_JS = (
    "() => {\n"
    + _DIG_STATE_JS
    + "\n"
    + _PICK_RAW_JS
    + f"""
  const s = window[{_js(_GLOBAL_NAME)}];
  if (!s) return false;
  const mapWrap = digState(s, {_js(_NOTE_DETAIL_MAP_PATH)});
  if (!mapWrap) return false;
  const map = pickRaw(mapWrap);
  return !!(map && typeof map === 'object' && Object.keys(map).length > 0);
}}
"""
)

DETAIL_JS = (
    "(noteId) => {\n"
    + _UNWRAP_JS
    + "\n"
    + _DIG_STATE_JS
    + f"""
  const s = window[{_js(_GLOBAL_NAME)}];
  const mapWrap = s ? digState(s, {_js(_NOTE_DETAIL_MAP_PATH)}) : undefined;
  if (!mapWrap) return {{ ready: false, note: null }};
  const map = unwrap(mapWrap, 0) || {{}};
  const note = map[noteId] || map[Object.keys(map)[0]] || null;
  return {{ ready: !!note, note }};
}}
"""
)

DOM_DETAIL_JS = (
    "(arg) => {\n"
    + f"""
  const noteId = typeof arg === 'string' ? arg : String((arg && arg.noteId) || '');
  const dom = (arg && typeof arg === 'object' && arg.dom) ? arg.dom : {_DETAIL_DOM_JSON};
  const href = location.href || '';
  if (dom.blocked_url && new RegExp(dom.blocked_url).test(href)) {{
    return {{ ready: false, blocked: true, note: null }};
  }}
  let idFromUrl = noteId || '';
  if (dom.id_pattern) {{
    const m = href.match(new RegExp(dom.id_pattern, 'i'));
    if (m && m[1]) idFromUrl = m[1];
  }}

  const authorEl = dom.author ? document.querySelector(dom.author) : null;
  const nick = authorEl ? (authorEl.textContent || '').trim() : '';

  let title = '';
  const titleEl = dom.title ? document.querySelector(dom.title) : null;
  if (titleEl) title = (titleEl.textContent || '').trim();
  if (!title && dom.title_suffix_strip) {{
    title = (document.title || '').replace(new RegExp(dom.title_suffix_strip, 'u'), '').trim();
  }}
  const noise = dom.title_noise || [];
  const badTitle = !title || noise.some((n) => (typeof n === 'string' && (n.startsWith('^') || n.endsWith('$') ? new RegExp(n, 'u').test(title) : title.includes(n))));
  if (badTitle) {{
    return {{ ready: false, blocked: false, note: null }};
  }}

  const hasCard = !!(
    authorEl
    || (dom.card && document.querySelector(dom.card))
  );
  if (!hasCard && dom.id_pattern && !new RegExp(dom.id_pattern, 'i').test(href)) {{
    return {{ ready: false, blocked: false, note: null }};
  }}

  const noteObj = {{}};
  noteObj[dom.note_id_key || 'noteId'] = idFromUrl;
  noteObj.title = title;
  noteObj.user = {{}};
  noteObj.user[dom.user_nick_key || 'nickname'] = nick;
  return {{
    ready: true,
    blocked: false,
    note: noteObj,
  }};
}}
"""
)

DETAIL_HINT_JS = r"""
(opts) => {
  const dom = (opts && opts.dom) || {};
  const params = new URLSearchParams(location.search || '');
  const codeKey = dom.error_code_param || 'error_code';
  const msgKey = dom.error_msg_param || 'error_msg';
  return {
    url: location.href || '',
    title: document.title || '',
    error_code: params.get(codeKey) || '',
    error_msg: params.get(msgKey) || '',
    hasCard: !!(dom.card && document.querySelector(dom.card)),
  };
}
"""

SCROLL_COMMENTS_JS = (
    "(opts) => {\n"
    + f"""
  const dom = (opts && opts.dom) || {_COMMENTS_DOM_JSON};
  const sels = dom.scroll || [];
  for (const sel of sels) {{
    const el = document.querySelector(sel);
    if (el && typeof el.scrollTop === 'number') {{
      el.scrollTop = el.scrollHeight;
      return sel;
    }}
  }}
  const px = dom.scroll_fallback_px || 0;
  if (px) window.scrollBy(0, px);
  return dom.scroll_fallback_label || 'window';
}}
"""
)

DOM_COMMENTS_JS = (
    "(opts) => {\n"
    + f"""
  const dom = (opts && opts.dom) || {_COMMENTS_DOM_JSON};
  const behaviorAnon = {_js(str(_BEHAVIOR.get("anonymous_author") or ""))};
  const out = [];
  const limit = dom.limit || 0;
  const nodes = dom.item ? document.querySelectorAll(dom.item) : [];
  for (const node of nodes) {{
    const contentEl = dom.content ? node.querySelector(dom.content) : null;
    const authorEl = dom.author ? node.querySelector(dom.author) : null;
    const content = ((contentEl && contentEl.textContent) || '').trim();
    if (!content) continue;
    const author = ((authorEl && authorEl.textContent) || '').trim() || behaviorAnon;
    out.push({{ author, content, time: null, reply: null }});
    if (limit > 0 && out.length >= limit) break;
  }}
  return out;
}}
"""
)



def _card(row: dict[str, Any], api: dict[str, Any]) -> dict[str, Any]:
    for key in path_list(api, "card_keys"):
        card = row.get(key)
        if isinstance(card, dict):
            return card
    return {}


def _note_id(row: dict[str, Any], api: dict[str, Any]) -> str:
    paths = path_list(_fields(api), "item_id")
    found = dig_str(row, paths)
    if found:
        return found
    return dig_str(_card(row, api), paths)


def _title(row: dict[str, Any], api: dict[str, Any]) -> str:
    paths = path_list(_fields(api), "title")
    found = dig_str(row, paths)
    if found:
        return found
    return dig_str(_card(row, api), paths)


def _seller(row: dict[str, Any], api: dict[str, Any]) -> str:
    paths = path_list(_fields(api), "seller")
    found = dig_str(row, paths)
    if found:
        return found
    return dig_str(_card(row, api), paths)


def _xsec_token(row: dict[str, Any], api: dict[str, Any]) -> str:
    paths = path_list(_fields(api), "xsec_token")
    found = dig_str(row, paths)
    if found:
        return found
    return dig_str(_card(row, api), paths)


def _cover(row: dict[str, Any], api: dict[str, Any]) -> str:
    paths = path_list(_fields(api), "cover")
    for source in (row, _card(row, api)):
        value = dig_first(source, paths)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _note_type_values(kind: str) -> set[str]:
    rows = path_list(_sec("list_api"), f"note_type_{kind}")
    return {str(x).strip().lower() for x in rows}


def _note_type(row: dict[str, Any], api: dict[str, Any]) -> str:
    paths = path_list(_fields(api), "note_type")
    video_vals = _note_type_values("video")
    normal_vals = _note_type_values("normal")
    list_api = _sec("list_api")
    out_video = str(list_api.get("normalized_video") or "video")
    out_normal = str(list_api.get("normalized_normal") or "normal")
    card = _card(row, api)
    for source in (row, card):
        value = dig_first(source, paths)
        if value is None:
            continue
        text = str(value).strip().lower()
        if text in video_vals:
            return out_video
        if text in normal_vals:
            return out_normal
    return ""


def is_video_note(raw: Mapping[str, Any] | None) -> bool:
    """判断列表/详情 raw 是否视频笔记（暂不拉详情 OCR）。"""
    if not isinstance(raw, dict):
        return False
    list_api = _sec("list_api")
    video_vals = _note_type_values("video")
    out_video = str(list_api.get("normalized_video") or "video")
    note_type = str(raw.get("note_type") or "").strip().lower()
    if note_type in video_vals:
        return True
    if str(raw.get("skipped_reason") or "").strip().lower() in video_vals:
        return True
    feed = raw.get("feed")
    if isinstance(feed, dict) and _note_type(feed, list_api) == out_video:
        return True
    note = raw.get("note")
    detail_api = _sec("detail_api")
    if isinstance(note, dict) and _note_type(note, detail_api) == out_video:
        return True
    return False


def _note_image_urls(note: dict[str, Any]) -> list[str]:
    """从笔记详情结构抽出图片 URL（封面 + image_keys）。"""
    detail_api = _sec("detail_api")
    list_api = _sec("list_api")
    out: list[str] = []
    seen: set[str] = set()

    def _add(url: Any) -> None:
        text = str(url or "").strip()
        if not text.startswith("http") or text in seen:
            return
        seen.add(text)
        out.append(text)

    cover_val = dig_first(note, path_list(_fields(list_api), "cover"))
    if isinstance(cover_val, str):
        _add(cover_val)

    for key in path_list(detail_api, "image_keys"):
        blob = note.get(key)
        if not isinstance(blob, list):
            continue
        for row in blob:
            if isinstance(row, str):
                _add(row)
                continue
            if not isinstance(row, dict):
                continue
            _add(dig_first(row, path_list(detail_api, "image_url_paths")))

    return out


def _note_desc(note: dict[str, Any]) -> str:
    """笔记正文描述。"""
    detail_api = _sec("detail_api")
    return dig_str(note, path_list(_fields(detail_api), "desc"))


def _resolve_detail_blob(payload: dict[str, Any]) -> dict[str, Any]:
    """详情 payload（JS / feed / DOM）归一化为笔记 dict。"""
    detail_api = _sec("detail_api")
    fields = _fields(detail_api)
    title_paths = path_list(fields, "title")
    id_paths = path_list(fields, "item_id")

    wrapper = payload.get("note")
    if isinstance(wrapper, dict):
        blob: dict[str, Any] = wrapper
    elif isinstance(payload, dict):
        blob = payload
    else:
        return {}

    if not dig_str(blob, title_paths) and not dig_str(blob, id_paths):
        rows = dig_first(blob, path_list(detail_api, "rows"))
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            card = _card(rows[0], detail_api)
            blob = card if card else rows[0]

    card = _card(blob, detail_api)
    if card and (dig_str(card, title_paths) or dig_str(card, id_paths)):
        return card
    return blob if isinstance(blob, dict) else {}


def items_from_feeds(payload: dict[str, Any] | list[Any], *, limit: int) -> list[CrawlItem]:
    """搜索 feeds → CrawlItem 列表；行路径见 extract.json list_api.rows。"""
    list_api = _sec("list_api")
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = dig_first(payload, path_list(list_api, "rows"))
        if not isinstance(rows, list):
            rows = []
    else:
        return []
    out: list[CrawlItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        note_id = _note_id(row, list_api)
        title = _title(row, list_api)
        if not note_id or not title:
            continue
        out.append(
            CrawlItem(
                item_id=note_id,
                title=title,
                url=f"{NOTE_URL}/{note_id}",
                price=None,
                raw={
                    "seller_nick": _seller(row, list_api),
                    "xsec_token": _xsec_token(row, list_api),
                    "image_url": _cover(row, list_api),
                    "note_type": _note_type(row, list_api) or None,
                    "feed": row,
                },
            )
        )
        if len(out) >= limit:
            break
    return out


def item_from_detail(payload: dict[str, Any], note_id: str) -> CrawlItem:
    """详情弹层 / noteDetailMap / feed 一条 → CrawlItem。"""
    detail_api = _sec("detail_api")
    list_api = _sec("list_api")
    fields = _fields(detail_api)
    inner = _resolve_detail_blob(payload)
    resolved_id = _note_id(inner, detail_api) or str(note_id)
    title = _title(inner, detail_api)
    nick = _seller(inner, detail_api)
    token = _xsec_token(inner, detail_api)
    liked = dig_str(inner, path_list(fields, "liked"))
    collected = dig_str(inner, path_list(fields, "collected"))
    image_urls = _note_image_urls(inner)
    desc = _note_desc(inner)
    cover = image_urls[0] if image_urls else _cover(inner, list_api)
    note_type = _note_type(inner, detail_api) or _note_type(payload, list_api)
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
            "note_type": note_type or None,
            "note": inner,
        },
    )


def comments_from_api(body: Mapping[str, Any] | None) -> list[dict[str, str | None]]:
    """comment/page 响应 → [{author, content, time, reply}]。"""
    cfg = _sec("comment_api")
    fields = _fields(cfg)
    if not isinstance(body, dict):
        return []
    rows = dig_first(body, path_list(cfg, "rows"))
    if not isinstance(rows, list):
        return []

    out: list[dict[str, str | None]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        content = dig_str(row, path_list(fields, "content"))
        if not content:
            continue
        author = dig_str(row, path_list(fields, "author")) or str(cfg.get("anonymous_author") or "")
        time_text = _comment_time(dig_first(row, path_list(fields, "time")))
        reply = _first_sub_comment(row, fields)
        out.append(
            {
                "author": author,
                "content": content,
                "time": time_text,
                "reply": reply,
            }
        )
    return out


def comments_from_captured(bodies: list[Mapping[str, Any]]) -> list[dict[str, str | None]]:
    """多页 comment/page 合并去重。"""
    seen: set[str] = set()
    out: list[dict[str, str | None]] = []
    for body in bodies:
        for row in comments_from_api(body):
            key = f"{row.get('author')}|{row.get('content')}"
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out


def _first_sub_comment(row: Mapping[str, Any], fields: dict[str, Any]) -> str | None:
    """取首条子评论正文。"""
    subs = dig_first(row, path_list(fields, "replies"))
    if not isinstance(subs, list) or not subs:
        return None
    first = subs[0] if isinstance(subs[0], dict) else None
    if not first:
        return None
    text = dig_str(first, path_list(fields, "reply_content"))
    return text or None


def _comment_time(value: Any) -> str | None:
    """评论时间：毫秒时间戳或原文案。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            return str(int(value))
    text = str(value).strip()
    return text or None
