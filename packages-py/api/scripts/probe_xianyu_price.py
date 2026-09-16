"""探针：打印闲鱼商品详情页里所有与价格相关的原始值。

职责：
    排障用。打开商品页，分别取
    ① 页内 mtop（VIEW_JS）抽取出的 price / original_price 及 item 上所有 price 键；
    ② 页面上真实渲染出来的价格文案。
    用于判断「详情价格取错字段」时到底取到了什么。

使用示例：
    python -m api.scripts.probe_xianyu_price 1055636729652
"""

from __future__ import annotations

import asyncio
import json
import sys

from browser.manager import get_browser_manager
from contracts.browser_port import LaunchOptions
from crawler.core.base import BrowserSessionOptions
from crawler.core.types import CrawlContext
from crawler.registry import cookies_for
from crawler.sources.xianyu.crawler import XianyuCrawler
from crawler.sources.xianyu.extractor import ITEM_URL, VIEW_JS, view_arg
from tools.account_cookie import resolve_crawl_cookie

_PRICE_KEYS_JS = """
(itemId) => {
  const out = [];
  const walk = (node, path) => {
    if (!node || typeof node !== 'object') return;
    for (const [k, v] of Object.entries(node)) {
      if (v === null || v === undefined) continue;
      if (typeof v === 'object') { walk(v, path + '.' + k); continue; }
      if (k.toLowerCase().includes('price')) out.push(path + '.' + k + ' = ' + String(v));
    }
  };
  const state = window.__INITIAL_STATE__ || {};
  walk(state.detail || state.item || state, 'state');
  return out.slice(0, 40);
}
"""

_DOM_PRICE_JS = """
() => Array.from(document.querySelectorAll('[class*="price"],[class*="Price"]'))
  .map((el) => (el.innerText || '').replace(/\\s+/g, ' ').trim())
  .filter((t) => t && t.length < 40)
  .slice(0, 20)
"""


async def _main(item_id: str) -> int:
    cookie = resolve_crawl_cookie("xianyu")
    if not cookie:
        print("no cookie")
        return 1
    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=True))
    try:
        crawler = XianyuCrawler(
            port,
            BrowserSessionOptions(cookies=cookies_for("xianyu", cookie)),
        )
        ctx = CrawlContext(task_id="probe-price", meta={"cookie": cookie})
        page = await crawler.open_page(ctx)
        try:
            raw = page.raw
            await page.goto(ITEM_URL, params={"id": item_id})
            await raw.wait_for_timeout(3000)
            payload = await raw.evaluate(VIEW_JS, view_arg(item_id))
            print("== VIEW_JS price ==")
            print("price         =", json.dumps(payload.get("price"), ensure_ascii=False))
            print("original_price=", json.dumps(payload.get("original_price"), ensure_ascii=False))
            print("title         =", str(payload.get("title"))[:40])
            print("== state price keys ==")
            for line in await raw.evaluate(_PRICE_KEYS_JS, item_id):
                print(" ", line)
            print("== DOM price text ==")
            for line in await raw.evaluate(_DOM_PRICE_JS):
                print(" ", json.dumps(line, ensure_ascii=False))
        finally:
            await crawler.close_page(page)
    finally:
        await manager.release(port)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv[1] if len(sys.argv) > 1 else "")))
