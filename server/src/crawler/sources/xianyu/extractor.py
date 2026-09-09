"""闲鱼搜索页 DOM 抽取与 mtop 详情解析。

职责：
    提供 EXTRACT_JS / SCROLL_JS 页面脚本，及 items_from_payload、item_from_mtop_detail
    将原始 payload 标准化为 CrawlItem。

设计说明：
    - 移植自 goofish_cli search；仅服务于 crawler/sources/xianyu/crawler
    - 不含 Browser 启动或 Agent 逻辑
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.crawler.core.types import CrawlItem

logger = logging.getLogger("dingda.crawler.xianyu.extractor")

_ITEM_ID = re.compile(r"[?&]id=(\d+)")

# 页面上下文里跑的 JS（与 goofish_cli commands/search/search.py 对齐）
EXTRACT_JS = r"""
(limit) => (async () => {
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
    for (const img of card.querySelectorAll('img')) {
      const src = absUrl(
        img.currentSrc || img.src || img.getAttribute('data-src') || ''
      );
      if (src) return src;
    }
    return '';
  };
  const sel = {
    card: 'a[href*="/item?id="]',
    title: '[class*="row1-wrap-title"], [class*="main-title"]',
    attrs: '[class*="row2-wrap-cpv"] span[class*="cpv--"]',
    priceWrap: '[class*="price-wrap"]',
    priceNum: '[class*="number"]',
    priceDec: '[class*="decimal"]',
    priceDesc: '[class*="price-desc"] [title], [class*="price-desc"] [style*="line-through"]',
    sellerWrap: '[class*="row4-wrap-seller"]',
    sellerText: '[class*="seller-text"]',
    badge: '[class*="credit-container"] [title], [class*="credit-container"] span',
  };

  await waitFor(() => {
    const bodyText = document.body?.innerText || '';
    return Boolean(
      document.querySelector(sel.card)
      || /请先登录|登录后|验证码|安全验证|异常访问/.test(bodyText)
      || /暂无相关宝贝|未找到相关宝贝|没有找到/.test(bodyText)
    );
  });

  const bodyText = document.body?.innerText || '';
  const requiresAuth = /请先登录|登录后/.test(bodyText);
  const blocked = /验证码|安全验证|异常访问/.test(bodyText);
  const empty = /暂无相关宝贝|未找到相关宝贝|没有找到/.test(bodyText);

  const items = Array.from(document.querySelectorAll(sel.card))
    .slice(0, limit)
    .map((card) => {
      const href = card.href || card.getAttribute('href') || '';
      const title = clean(card.querySelector(sel.title)?.textContent || '');
      const attrs = Array.from(card.querySelectorAll(sel.attrs))
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
                    url = _abs_image_url(entry.get("url") or entry.get("picUrl"))
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


ITEM_URL = "https://www.goofish.com/item"

# 商品页内 lib.mtop.request（对齐 goofish_cli item view）
VIEW_JS = r"""
(itemId) => (async () => {
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
  if (/验证码|安全验证|异常访问/.test(bodyText)) return { error: 'blocked' };

  await waitFor(() => window.lib?.mtop?.request);
  if (!window.lib || !window.lib.mtop || typeof window.lib.mtop.request !== 'function') {
    return { error: 'mtop-not-ready' };
  }

  let response;
  try {
    response = await window.lib.mtop.request({
      api: 'mtop.taobao.idle.pc.detail',
      data: { itemId: String(itemId) },
      type: 'POST',
      v: '1.0',
      dataType: 'json',
      needLogin: false,
      needLoginPC: false,
      sessionOption: 'AutoLoginOnly',
      ecode: 0,
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
  if (retCode && retCode !== 'SUCCESS') {
    return {
      error: 'mtop-response-error',
      error_code: retCode,
      error_message: clean((response?.ret || []).join(' | ')),
    };
  }

  const data = response?.data || {};
  const item = data.itemDO || {};
  const seller = data.sellerDO || {};
  const labels = Array.isArray(item.itemLabelExtList) ? item.itemLabelExtList : [];
  const findLabel = (name) => labels.find((l) => clean(l.propertyText) === name)?.text || '';
  const images = Array.isArray(item.imageInfos)
    ? item.imageInfos.map((e) => e?.url).filter(Boolean)
    : [];

  return {
    item_id: clean(item.itemId || itemId),
    title: clean(item.title || ''),
    description: clean(item.desc || ''),
    price: clean('¥' + (item.soldPrice || item.defaultPrice || '')).replace(/^¥\s*$/, ''),
    original_price: clean(item.originalPrice || ''),
    want_count: String(item.wantCnt ?? ''),
    collect_count: String(item.collectCnt ?? ''),
    browse_count: String(item.browseCnt ?? ''),
    status: clean(item.itemStatusStr || ''),
    condition: clean(findLabel('成色')),
    brand: clean(findLabel('品牌')),
    category: clean(findLabel('分类')),
    location: clean(seller.publishCity || seller.city || ''),
    seller_name: clean(seller.nick || seller.uniqueName || ''),
    seller_id: String(seller.sellerId || ''),
    seller_score: clean(seller.xianyuSummary || ''),
    reply_ratio_24h: clean(seller.replyRatio24h || ''),
    reply_interval: clean(seller.replyInterval || ''),
    image_urls: images,
  };
})()
"""


def item_from_view(payload: dict[str, Any], item_id: str) -> CrawlItem:
    """页内 mtop 抽取结果 → CrawlItem。"""
    resolved_id = str(payload.get("item_id") or item_id)
    title = str(payload.get("title") or "")
    price = payload.get("price") or ""
    want = str(payload.get("want_count") or "").strip()
    return CrawlItem(
        item_id=resolved_id,
        title=title,
        url=f"{ITEM_URL}?id={resolved_id}",
        price=str(price) if price not in (None, "") else None,
        raw={
            "seller_nick": payload.get("seller_name", ""),
            "status": payload.get("status", ""),
            "want_count": want or None,
            "browse_count": str(payload.get("browse_count") or "").strip() or None,
            "collect_count": str(payload.get("collect_count") or "").strip() or None,
            "image_url": _first_image_url(payload.get("image_urls"), payload.get("image_url")),
            "view": payload,
        },
    )


def item_from_mtop_detail(raw: dict[str, Any], item_id: str) -> CrawlItem:
    """mtop.taobao.idle.pc.detail 原始 JSON → CrawlItem（优先 itemDO）。"""
    data = raw.get("data") if isinstance(raw, dict) else None
    data = data if isinstance(data, dict) else {}
    item_do = data.get("itemDO") if isinstance(data.get("itemDO"), dict) else {}
    seller_do = data.get("sellerDO") if isinstance(data.get("sellerDO"), dict) else {}
    track = data.get("trackParams") if isinstance(data.get("trackParams"), dict) else {}

    resolved_id = str(item_do.get("itemId") or track.get("id") or item_id)
    title = str(item_do.get("title") or track.get("title") or "")
    sold = item_do.get("soldPrice") or item_do.get("defaultPrice") or track.get("soldPrice") or track.get("price")
    price = f"¥{sold}" if sold not in (None, "") else ""
    if price == "¥":
        price = ""
    want = item_do.get("wantCnt")
    want_count = str(want) if want not in (None, "") else None
    seller = str(seller_do.get("nick") or seller_do.get("uniqueName") or track.get("seller_nick") or "")
    status = str(item_do.get("itemStatusStr") or track.get("itemStatus") or "")
    url = f"https://www.goofish.com/item?id={resolved_id}"
    return CrawlItem(
        item_id=resolved_id,
        title=title,
        url=url,
        price=price or None,
        raw={
            "seller_nick": seller,
            "status": status,
            "want_count": want_count,
            "browse_count": str(item_do["browseCnt"]) if item_do.get("browseCnt") not in (None, "") else None,
            "collect_count": str(item_do["collectCnt"]) if item_do.get("collectCnt") not in (None, "") else None,
            "image_url": _first_image_url(item_do.get("imageInfos"), item_do.get("picUrl")),
            "mtop": raw,
        },
    )
