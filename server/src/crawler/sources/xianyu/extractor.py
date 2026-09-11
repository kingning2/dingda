"""闲鱼搜索页 DOM 抽取与 mtop 搜索/详情解析。

职责：
    提供 EXTRACT_JS / SCROLL_JS / VIEW_JS / DETAIL_DOM_JS，及 payload / mtop 标准化为 CrawlItem。
    选择器、API 名、字段路径一律来自同目录 ``extract.json``，禁止写死平台特例。

设计说明：
    - 仅服务于 crawler/sources/xianyu/crawler
    - 不含 Browser 启动或 Agent 逻辑
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.crawler.core.types import CrawlItem
from src.crawler.extraction.config import (
    dig,
    dig_first,
    dig_str,
    load_extract_json,
    path_list,
    section,
)

logger = logging.getLogger("dingda.crawler.xianyu.extractor")

EXTRACT = load_extract_json(__file__)
_URLS = section(EXTRACT, "urls")
ITEM_URL = str(_URLS.get("item") or "")
SEARCH_URL = str(_URLS.get("search") or "")
_ITEM_ID = re.compile(str(_URLS.get("item_id_pattern") or r"[?&]id=(\d+)"))


def _sec(name: str) -> dict[str, Any]:
    """读最新缓存中的小节（写回 extract.json 后立即生效）。"""
    return section(load_extract_json(__file__), name)


def search_dom_arg(limit: int) -> dict[str, Any]:
    """``page.evaluate(EXTRACT_JS, …)``：limit + extract.json dom/signals。"""
    return {
        "limit": int(limit),
        "dom": _sec("dom"),
        "signals": _sec("signals"),
    }


def view_arg(item_id: str) -> dict[str, Any]:
    """``page.evaluate(VIEW_JS, …)``：itemId + view/signals。"""
    return {
        "itemId": str(item_id),
        "view": _sec("view"),
        "signals": _sec("signals"),
    }


def detail_dom_arg(item_id: str) -> dict[str, Any]:
    """``page.evaluate(DETAIL_DOM_JS, …)``：itemId + detail_dom/signals。"""
    return {
        "itemId": str(item_id),
        "dom": _sec("detail_dom"),
        "signals": _sec("signals"),
    }


def list_api_name() -> str:
    """闲鱼搜索列表 mtop API 名。"""
    return dig_str(EXTRACT, ["list_api.api"])


def cookie_domain() -> str:
    """浏览器 cookie 域名。"""
    return str(_URLS.get("cookie_domain") or "")


def list_api_meta() -> dict[str, Any]:
    """列表 mtop：version / spm / 分页 / 请求体键。"""
    cfg = _sec("list_api")
    return {
        "version": str(cfg.get("version") or ""),
        "spm_cnt": str(cfg.get("spm_cnt") or ""),
        "page_size": int(cfg["page_size"]) if isinstance(cfg.get("page_size"), int) else 0,
        "max_pages": int(cfg["max_pages"]) if isinstance(cfg.get("max_pages"), int) else 0,
        "request_keys": cfg.get("request_keys") if isinstance(cfg.get("request_keys"), dict) else {},
        "request_static": cfg.get("request_static") if isinstance(cfg.get("request_static"), dict) else {},
        "rows": path_list(cfg, "rows"),
        "price_part_keys": path_list(cfg, "price_part_keys"),
    }


def detail_api_meta() -> dict[str, Any]:
    """详情 mtop：api / version / spm / data key。"""
    cfg = _sec("detail_api")
    return {
        "api": str(cfg.get("api") or ""),
        "version": str(cfg.get("version") or ""),
        "spm_cnt": str(cfg.get("spm_cnt") or ""),
        "data_item_id_key": str(cfg.get("data_item_id_key") or ""),
    }


def comment_api_meta() -> dict[str, Any]:
    """留言 mtop：api / page_size / 请求体键。"""
    cfg = _sec("comment_api")
    keys = cfg.get("request_keys") if isinstance(cfg.get("request_keys"), dict) else {}
    return {
        "api": str(cfg.get("api") or ""),
        "version": str(cfg.get("version") or ""),
        "page_size": int(cfg["page_size"]) if isinstance(cfg.get("page_size"), int) else 0,
        "request_keys": keys,
        "first_page": int(cfg["first_page"]) if isinstance(cfg.get("first_page"), int) else 1,
        "anonymous_author": str(cfg.get("anonymous_author") or ""),
    }


def limits_meta() -> dict[str, int]:
    """默认 / 上限条数。"""
    cfg = _sec("limits")
    return {
        "default_limit": int(cfg["default_limit"]) if isinstance(cfg.get("default_limit"), int) else 20,
        "max_limit": int(cfg["max_limit"]) if isinstance(cfg.get("max_limit"), int) else 100,
    }


def session_expired_markers() -> tuple[str, ...]:
    """页内 mtop 会话过期标记。"""
    return tuple(path_list(_sec("signals"), "session_expired"))


def build_list_request(*, page: int, query: str, rows: int) -> dict[str, Any]:
    """按 extract.json 拼列表 mtop data。"""
    meta = list_api_meta()
    keys = meta["request_keys"]
    data = dict(meta["request_static"])
    data[str(keys["page"])] = page
    data[str(keys["keyword"])] = query
    data[str(keys["rows"])] = rows
    return data


def build_comment_request(*, item_id: str) -> dict[str, Any]:
    """按 extract.json 拼留言 mtop data。"""
    meta = comment_api_meta()
    keys = meta["request_keys"]
    return {
        str(keys["item_id"]): str(item_id),
        str(keys["page"]): int(meta["first_page"]),
        str(keys["page_size"]): int(meta["page_size"]),
    }


# 选择器由 evaluate 参数注入（extract.json → dom）
EXTRACT_JS = r"""
(opts) => (async () => {
  const limit = opts.limit;
  const sel = opts.dom || {};
  const signals = opts.signals || {};
  const hit = (keys) => {
    const bodyText = document.body?.innerText || '';
    return (keys || []).some((k) => bodyText.includes(k));
  };

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const waitFor = async (predicate, timeoutMs = 8000) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (predicate()) return true;
      await wait(150);
    }
    return false;
  };

  const clean = (v) => (v || '').replace(/\s+/g, ' ').trim();
  const absUrl = (v) => {
    const s = clean(v);
    if (!s || s.startsWith('data:')) return '';
    if (s.startsWith('//')) return 'https:' + s;
    return s;
  };
  const pickImage = (card) => {
    const imgSel = sel.img || 'img';
    const attrs = sel.img_attrs || ['src'];
    for (const img of card.querySelectorAll(imgSel)) {
      let src = '';
      for (const attr of attrs) {
        if (attr === 'currentSrc') src = absUrl(img.currentSrc || '');
        else if (attr === 'src') src = absUrl(img.src || '');
        else src = absUrl(img.getAttribute(attr) || '');
        if (src) return src;
      }
    }
    return '';
  };

  await waitFor(() => {
    return Boolean(
      (sel.card && document.querySelector(sel.card))
      || hit(signals.requires_auth)
      || hit(signals.blocked)
      || hit(signals.empty)
    );
  });

  const bodyText = document.body?.innerText || '';
  const requiresAuth = hit(signals.requires_auth);
  const blocked = hit(signals.blocked);
  const empty = hit(signals.empty);

  const items = Array.from(document.querySelectorAll(sel.card || ''))
    .slice(0, limit)
    .map((card) => {
      const href = card.href || card.getAttribute('href') || '';
      const title = clean(card.querySelector(sel.title)?.textContent || '');
      const attrs = Array.from(card.querySelectorAll(sel.attrs || sel.empty_selector || '.__none__'))
        .map((n) => clean(n.textContent || ''))
        .filter(Boolean);
      const priceWrap = card.querySelector(sel.priceWrap);
      const priceNumber = clean(priceWrap?.querySelector(sel.priceNum)?.textContent || '');
      const priceDecimal = clean(priceWrap?.querySelector(sel.priceDec)?.textContent || '');
      const location = clean(card.querySelector(sel.sellerWrap)?.querySelector(sel.sellerText)?.textContent || '');
      const originalPriceNode = card.querySelector(sel.priceDesc);
      const badgeNode = card.querySelector(sel.badge);

      return {
        title,
        url: href,
        price: clean('¥' + priceNumber + priceDecimal).replace(/^¥\s*$/, ''),
        original_price: clean(originalPriceNode?.getAttribute('title') || originalPriceNode?.textContent || ''),
        condition: attrs[0] || '',
        brand: attrs[1] || '',
        extra: attrs.slice(2).join(' | '),
        location,
        badge: clean(badgeNode?.getAttribute('title') || badgeNode?.textContent || ''),
        image_url: pickImage(card),
      };
    })
    .filter((it) => it.title && it.url);

  return { requiresAuth, blocked, empty, items, bodyPreview: bodyText.slice(0, 500) };
})()
"""

SCROLL_JS = """
(times) => (async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < times; i++) {
    window.scrollBy(0, window.innerHeight);
    await wait(400);
  }
})()
"""

# 页内 lib.mtop；api / 字段键来自 extract.json → view
VIEW_JS = r"""
(opts) => (async () => {
  const itemId = opts.itemId;
  const view = opts.view || {};
  const signals = opts.signals || {};
  const fields = view.fields || {};
  const labelNames = view.label_names || {};
  const propKey = view.label_property_key || 'propertyText';
  const textKey = view.label_text_key || 'text';
  const imageUrlKey = view.image_url_key || 'url';
  const pick = (obj, keys) => {
    for (const k of (keys || [])) {
      const v = obj?.[k];
      if (v !== undefined && v !== null && String(v).trim() !== '') return v;
    }
    return '';
  };
  const clean = (v) => String(v ?? '').replace(/\s+/g, ' ').trim();
  const extractRetCode = (ret) => {
    const first = Array.isArray(ret) ? ret[0] : '';
    return clean(first).split('::')[0] || '';
  };
  const waitFor = async (predicate, timeoutMs = 5000) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (predicate()) return true;
      await new Promise((r) => setTimeout(r, 150));
    }
    return false;
  };

  const bodyText = document.body?.innerText || '';
  if ((signals.blocked || []).some((k) => bodyText.includes(k))) {
    return { error: 'blocked' };
  }

  await waitFor(() => window.lib?.mtop?.request);
  if (!window.lib || !window.lib.mtop || typeof window.lib.mtop.request !== 'function') {
    return { error: 'mtop-not-ready' };
  }

  const dataKey = view.data_item_id_key || 'itemId';
  let response;
  try {
    response = await window.lib.mtop.request({
      api: view.api,
      data: { [dataKey]: String(itemId) },
      type: view.request_type || 'POST',
      v: view.version,
      dataType: view.data_type || 'json',
      needLogin: !!view.need_login,
      needLoginPC: !!view.need_login_pc,
      sessionOption: view.session_option || 'AutoLoginOnly',
      ecode: view.ecode ?? 0,
    });
  } catch (error) {
    const ret = error?.ret || [];
    return {
      error: 'mtop-request-failed',
      error_code: extractRetCode(ret),
      error_message: clean(Array.isArray(ret) ? ret.join(' | ') : error?.message || String(error)),
    };
  }

  const retCode = extractRetCode(response?.ret || []);
  const successCode = view.success_code || 'SUCCESS';
  if (retCode && retCode !== successCode) {
    return {
      error: 'mtop-response-error',
      error_code: retCode,
      error_message: clean((response?.ret || []).join(' | ')),
    };
  }

  const data = response?.data || {};
  const item = data[view.item] || {};
  const seller = data[view.seller] || {};
  const labels = Array.isArray(item[view.labels]) ? item[view.labels] : [];
  const findLabel = (name) => labels.find((l) => clean(l[propKey]) === name)?.[textKey] || '';
  const imageKey = view.images;
  const images = Array.isArray(item[imageKey])
    ? item[imageKey].map((e) => e?.[imageUrlKey]).filter(Boolean)
    : [];
  const sold = pick(item, fields.sold_price);

  return {
    item_id: clean(pick(item, fields.item_id) || itemId),
    title: clean(pick(item, fields.title) || ''),
    description: clean(pick(item, fields.desc) || ''),
    price: clean('¥' + sold).replace(/^¥\s*$/, ''),
    original_price: clean(pick(item, fields.original_price) || ''),
    want_count: String(pick(item, fields.want_count) ?? ''),
    collect_count: String(pick(item, fields.collect_count) ?? ''),
    browse_count: String(pick(item, fields.browse_count) ?? ''),
    status: clean(pick(item, fields.status) || ''),
    condition: clean(findLabel(labelNames.condition || '')),
    brand: clean(findLabel(labelNames.brand || '')),
    category: clean(findLabel(labelNames.category || '')),
    location: clean(pick(seller, fields.location) || ''),
    seller_name: clean(pick(seller, fields.seller_nick) || ''),
    seller_id: String(pick(seller, fields.seller_id) || ''),
    seller_score: clean(pick(seller, fields.seller_score) || ''),
    reply_ratio_24h: clean(pick(seller, fields.reply_ratio_24h) || ''),
    reply_interval: clean(pick(seller, fields.reply_interval) || ''),
    image_urls: images,
  };
})()
"""

# 详情 DOM 兜底；选择器来自 extract.json → detail_dom（探测文档见 DOM_PROBE.md）
DETAIL_DOM_JS = r"""
(opts) => (async () => {
  const itemId = opts.itemId;
  const sel = opts.dom || {};
  const signals = opts.signals || {};
  const clean = (v) => String(v ?? '').replace(/\s+/g, ' ').trim();
  const absUrl = (v) => {
    const s = clean(v);
    if (!s || s.startsWith('data:')) return '';
    if (s.startsWith('//')) return 'https:' + s;
    return s;
  };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const hit = (keys) => {
    const bodyText = document.body?.innerText || '';
    return (keys || []).some((k) => bodyText.includes(k));
  };
  const timeoutMs = Number(sel.ready_timeout_ms) || 8000;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (hit(signals.blocked) || hit(signals.requires_auth)) break;
    const info = sel.info && document.querySelector(sel.info);
    const priceEl = sel.price && document.querySelector(sel.price);
    const descEl = sel.desc && document.querySelector(sel.desc);
    if (info && (priceEl || descEl) && clean((descEl || info).innerText).length > 8) break;
    await wait(150);
  }

  if (hit(signals.blocked)) return { error: 'blocked' };
  if (hit(signals.requires_auth)) return { error: 'auth-required' };

  const info = (sel.info && document.querySelector(sel.info)) || null;
  const descEl = (sel.desc && document.querySelector(sel.desc)) || null;
  const priceEl = (sel.price && document.querySelector(sel.price)) || null;
  const wantEl = (sel.want && document.querySelector(sel.want)) || null;
  const nickEl = (sel.seller_nick && document.querySelector(sel.seller_nick)) || null;
  const introEl = (sel.seller_intro && document.querySelector(sel.seller_intro)) || null;

  let title = '';
  let description = '';
  if (descEl) {
    description = clean(descEl.innerText || '');
    const first = Array.from(descEl.querySelectorAll(':scope > span'))
      .map((n) => clean(n.innerText || ''))
      .find((t) => t.length >= 4);
    title = first || description.slice(0, 80);
  }
  if (!title && info) {
    title = clean(info.innerText || '').slice(0, 80);
  }

  const priceText = clean(priceEl?.innerText || '');
  const price = priceText ? clean('¥' + priceText).replace(/^¥\s*$/, '') : '';

  const wantBlob = clean(wantEl?.innerText || '');
  let want_count = '';
  let browse_count = '';
  try {
    const wm = wantBlob.match(new RegExp(sel.want_re || '([\\d.]+\\s*万?)\\s*人想要'));
    if (wm) want_count = clean(wm[1]);
    const bm = wantBlob.match(new RegExp(sel.browse_re || '([\\d.]+\\s*万?)\\s*浏览'));
    if (bm) browse_count = clean(bm[1]);
  } catch (_) {}
  if (!want_count && wantEl) {
    for (const child of wantEl.children || []) {
      const t = clean(child.innerText || '');
      if (/想要/.test(t)) want_count = t.replace(/人想要.*/, '').trim() || t;
      if (/浏览/.test(t)) browse_count = t.replace(/浏览.*/, '').trim() || t;
    }
  }

  const intro = clean(introEl?.innerText || '');
  const location = intro ? clean(intro.split(/\s+/)[0] || '') : '';

  const images = [];
  const imgSel = sel.img || 'img';
  const attrs = sel.img_attrs || ['currentSrc', 'src', 'data-src'];
  for (const img of document.querySelectorAll(imgSel)) {
    let src = '';
    for (const attr of attrs) {
      if (attr === 'currentSrc') src = absUrl(img.currentSrc || '');
      else if (attr === 'src') src = absUrl(img.src || '');
      else src = absUrl(img.getAttribute(attr) || '');
      if (src) break;
    }
    if (src && !images.includes(src)) images.push(src);
  }

  const labelsText = clean(
    ((sel.labels && document.querySelector(sel.labels)) || {})?.innerText || ''
  );
  let brand = '';
  const brandMatch = labelsText.match(/品牌\s*[:：]\s*([^\s]+)/);
  if (brandMatch) brand = clean(brandMatch[1]);

  if (!title && !description && !price) {
    return { error: 'dom-empty', item_id: String(itemId || '') };
  }

  return {
    item_id: String(itemId || ''),
    title,
    description,
    price,
    original_price: '',
    want_count,
    collect_count: '',
    browse_count,
    status: '',
    condition: '',
    brand,
    category: '',
    location,
    seller_name: clean(nickEl?.innerText || ''),
    seller_id: '',
    seller_score: '',
    reply_ratio_24h: '',
    reply_interval: '',
    image_urls: images,
    via: 'detail_dom',
  };
})()
"""


def item_id_from_url(url: str) -> str:
    """从商品 URL 抽出 item_id。"""
    match = _ITEM_ID.search(url or "")
    return match.group(1) if match else ""


def _abs_image_url(url: Any) -> str:
    """协议相对地址补 https；空/data URI 丢弃。"""
    text = str(url or "").strip()
    if not text or text.startswith("data:"):
        return ""
    if text.startswith("//"):
        return f"https:{text}"
    return text


def _first_image_url(*candidates: Any) -> str | None:
    """从若干候选里取第一张可用图（字符串或 imageInfos 列表）。"""
    entry_keys = path_list(_sec("image"), "entry_keys") or ["url", "picUrl"]
    for candidate in candidates:
        if isinstance(candidate, str):
            url = _abs_image_url(candidate)
            if url:
                return url
            continue
        if isinstance(candidate, list):
            for entry in candidate:
                if isinstance(entry, str):
                    url = _abs_image_url(entry)
                elif isinstance(entry, dict):
                    picked = ""
                    for key in entry_keys:
                        picked = _abs_image_url(entry.get(key))
                        if picked:
                            break
                    url = picked
                else:
                    url = ""
                if url:
                    return url
    return None


def items_from_payload(payload: dict[str, Any]) -> list[CrawlItem]:
    """把 evaluate 返回的 dict 收成 CrawlItem 列表。"""
    raw_items = payload.get("items") or []
    items: list[CrawlItem] = []
    for index, row in enumerate(raw_items):
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "")
        title = str(row.get("title") or "")
        item_id = item_id_from_url(url)
        if not item_id or not title:
            continue
        items.append(
            CrawlItem(
                item_id=item_id,
                title=title,
                url=url,
                price=str(row.get("price") or "") or None,
                raw={
                    "rank": index + 1,
                    "original_price": row.get("original_price"),
                    "condition": row.get("condition"),
                    "brand": row.get("brand"),
                    "extra": row.get("extra"),
                    "location": row.get("location"),
                    "badge": row.get("badge"),
                    "image_url": _first_image_url(row.get("image_url")),
                },
            )
        )
    logger.info("extract_search count=%s", len(items))
    return items


def items_from_mtop_search(raw: dict[str, Any], *, limit: int) -> list[CrawlItem]:
    """列表 mtop 响应 → CrawlItem；路径见 extract.json list_api。"""
    list_api = _sec("list_api")
    rows = dig_first(raw, path_list(list_api, "rows"))
    if not isinstance(rows, list):
        return []
    param = str(_URLS.get("item_id_param") or "")

    items: list[CrawlItem] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        parsed = _parse_mtop_search_card(row, list_api)
        if not parsed:
            continue
        item_id, title, price, image_url, location, seller = parsed
        items.append(
            CrawlItem(
                item_id=item_id,
                title=title,
                url=f"{ITEM_URL}?{param}={item_id}",
                price=price,
                raw={
                    "rank": index + 1,
                    "seller_nick": seller,
                    "location": location,
                    "image_url": image_url,
                    "mtop_search": row,
                },
            )
        )
        if len(items) >= limit:
            break
    logger.info("extract_mtop_search count=%s", len(items))
    return items


# 买家保障卡片的文案会被当成商品标题（card_roots 回退时命中保障卡）
_TITLE_NOISE = ("满足条件时，买家可退货且运费由卖家承担",)


def _title_is_noise(title: str) -> bool:
    """是不是保障卡的说明文案（不是商品名）。"""
    text = title.strip()
    return any(text.startswith(n) for n in _TITLE_NOISE)


def _parse_mtop_search_card(
    row: dict[str, Any],
    list_api: dict[str, Any],
) -> tuple[str, str, str | None, str | None, str | None, str | None] | None:
    """按 extract.json 的 card_roots / fields 解析单条搜索卡片。"""
    roots = path_list(list_api, "card_roots")
    fields = list_api.get("fields") if isinstance(list_api.get("fields"), dict) else {}
    main: dict[str, Any] | None = None
    for path in roots:
        candidate = dig(row, str(path))
        if isinstance(candidate, dict):
            main = candidate
            break
    if main is None:
        return None

    item_id = dig_str(main, path_list(fields, "item_id"))
    # 逐个 title 路径试，跳过保障卡文案
    title = ""
    for path in path_list(fields, "title"):
        candidate = dig_str(main, [path])
        if candidate and not _title_is_noise(candidate):
            title = candidate
            break
    if not item_id or not title:
        return None

    price = _format_mtop_price(
        dig_first(main, path_list(fields, "price")),
        path_list(list_api, "price_part_keys"),
    )
    image_url = _first_image_url(dig_first(main, path_list(fields, "image")))
    location = dig_str(main, path_list(fields, "location")) or None
    seller = dig_str(main, path_list(fields, "seller")) or None
    return item_id, title, price, image_url, location, seller


def _format_mtop_price(direct: Any, part_keys: list[str] | None = None) -> str | None:
    """搜索卡片价格字段（字符串或分段 price 列表）。"""
    keys = part_keys or path_list(_sec("list_api"), "price_part_keys") or ["text", "priceText"]
    if isinstance(direct, str) and direct.strip():
        text = direct.strip()
        return text if text.startswith("¥") else f"¥{text}"
    if isinstance(direct, (int, float)):
        return f"¥{direct}"
    if isinstance(direct, list):
        parts: list[str] = []
        for row in direct:
            if isinstance(row, dict):
                part = ""
                for key in keys:
                    part = str(row.get(key) or "").strip()
                    if part:
                        break
                parts.append(part)
            else:
                parts.append(str(row or "").strip())
        joined = "".join(p for p in parts if p)
        if joined:
            return joined if joined.startswith("¥") else f"¥{joined}"
    return None


def comments_from_mtop(raw: dict[str, Any]) -> list[dict[str, str | None]]:
    """mtop 留言列表 → [{author, content, time, reply}]；路径见 comment_api。"""
    cfg = _sec("comment_api")
    fields = cfg.get("fields") if isinstance(cfg.get("fields"), dict) else {}
    rows = dig_first(raw, path_list(cfg, "rows"))
    if not isinstance(rows, list):
        return []

    card_keys = path_list(cfg, "card_keys")
    anonymous = str(cfg.get("anonymous_author") or "")
    out: list[dict[str, str | None]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        card = row
        for key in card_keys:
            nested = row.get(key)
            if isinstance(nested, dict):
                card = nested
                break
        content = dig_str(card, path_list(fields, "content"))
        if not content:
            continue
        author = dig_str(card, path_list(fields, "author")) or anonymous
        time_text = dig_str(card, path_list(fields, "time")) or None
        reply = _first_reply_text(card, fields)
        out.append(
            {
                "author": author,
                "content": content,
                "time": time_text,
                "reply": reply,
            }
        )
    return out


def _first_reply_text(card: dict[str, Any], fields: dict[str, Any]) -> str | None:
    """取首条卖家/嵌套回复正文。"""
    replies = dig_first(card, path_list(fields, "replies"))
    if not isinstance(replies, list) or not replies:
        return None
    first = replies[0] if isinstance(replies[0], dict) else None
    if not first:
        return None
    text = dig_str(first, path_list(fields, "reply_content"))
    return text or None


def item_from_view(payload: dict[str, Any], item_id: str) -> CrawlItem:
    """页内 mtop 抽取结果 → CrawlItem。"""
    resolved_id = str(payload.get("item_id") or item_id)
    title = str(payload.get("title") or "")
    price = payload.get("price") or ""
    want = str(payload.get("want_count") or "").strip()
    desc = str(payload.get("description") or payload.get("desc") or "").strip() or None
    location = str(payload.get("location") or "").strip() or None
    param = str(_URLS.get("item_id_param") or "")
    return CrawlItem(
        item_id=resolved_id,
        title=title,
        url=f"{ITEM_URL}?{param}={resolved_id}",
        price=str(price) if price not in (None, "") else None,
        raw={
            "seller_nick": payload.get("seller_name", ""),
            "status": payload.get("status", ""),
            "want_count": want or None,
            "browse_count": str(payload.get("browse_count") or "").strip() or None,
            "collect_count": str(payload.get("collect_count") or "").strip() or None,
            "image_url": _first_image_url(payload.get("image_urls"), payload.get("image_url")),
            "desc": desc,
            "location": location,
            "view": payload,
        },
    )


def item_from_mtop_detail(raw: dict[str, Any], item_id: str) -> CrawlItem:
    """详情 mtop 原始 JSON → CrawlItem；路径见 detail_api。"""
    cfg = _sec("detail_api")
    fields = cfg.get("fields") if isinstance(cfg.get("fields"), dict) else {}
    item_do = dig_first(raw, path_list(cfg, "item"))
    seller_do = dig_first(raw, path_list(cfg, "seller"))
    track = dig_first(raw, path_list(cfg, "track"))
    item_do = item_do if isinstance(item_do, dict) else {}
    seller_do = seller_do if isinstance(seller_do, dict) else {}
    track = track if isinstance(track, dict) else {}

    id_paths = path_list(fields, "item_id")
    title_paths = path_list(fields, "title")
    resolved_id = dig_str(item_do, id_paths) or dig_str(track, id_paths) or str(item_id)
    title = dig_str(item_do, title_paths) or dig_str(track, title_paths)
    sold = dig_first(item_do, path_list(fields, "price"))
    if sold in (None, ""):
        sold = dig_first(track, path_list(fields, "price"))
    price = f"¥{sold}" if sold not in (None, "") else ""
    if price == "¥":
        price = ""
    want = dig_first(item_do, path_list(fields, "want_count"))
    want_count = str(want) if want not in (None, "") else None
    seller = dig_str(seller_do, path_list(fields, "seller_nick")) or dig_str(
        track, path_list(fields, "seller_nick")
    )
    status = dig_str(item_do, path_list(fields, "status")) or dig_str(
        track, path_list(fields, "status")
    )
    desc = dig_str(item_do, path_list(fields, "desc")) or None
    location = dig_str(seller_do, path_list(fields, "location")) or None
    browse = dig_first(item_do, path_list(fields, "browse_count"))
    collect = dig_first(item_do, path_list(fields, "collect_count"))
    param = str(_URLS.get("item_id_param") or "")
    return CrawlItem(
        item_id=resolved_id,
        title=title,
        url=f"{ITEM_URL}?{param}={resolved_id}",
        price=price or None,
        raw={
            "seller_nick": seller,
            "status": status,
            "want_count": want_count,
            "browse_count": str(browse) if browse not in (None, "") else None,
            "collect_count": str(collect) if collect not in (None, "") else None,
            "image_url": _first_image_url(dig_first(item_do, path_list(fields, "image"))),
            "desc": desc,
            "location": location,
            "mtop": raw,
        },
    )
