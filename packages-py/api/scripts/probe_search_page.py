"""探针：打印指定引擎下闲鱼搜索页的真实状态。

职责：
    排障用。用账号库 cookie 打开 goofish 搜索页，打印 URL、正文摘要、
    商品卡片数、登录/风控标记，用于判断「DOM 抽到 0 条」到底是页面没登录、
    被风控，还是选择器失效。

使用示例：
    DINGDA_BROWSER_ENGINE=chromium python -m api.scripts.probe_search_page 露营椅
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
from crawler.sources.xianyu.extractor import SEARCH_URL
from tools.account_cookie import resolve_crawl_cookie
from tools.headed import headless

_DIAG_JS = """
() => {
  const text = (document.body && document.body.innerText || '');
  const links = document.querySelectorAll('a[href*="item?id="]');
  const cards = document.querySelectorAll('[class*="feeds-item"], [class*="item-card"]');
  return {
    title: document.title,
    url: location.href,
    len: text.length,
    links: links.length,
    cards: cards.length,
    login: /请登录|登录后|扫码登录/.test(text),
    risk: /验证|滑块|安全验证|挤爆/.test(text),
    head: text.replace(/\\s+/g, ' ').slice(0, 500),
  };
}
"""


async def _main(query: str) -> int:
    cookie = resolve_crawl_cookie("xianyu")
    if not cookie:
        print("no cookie")
        return 1
    manager = get_browser_manager()
    print(f"engine = {manager.engine}")
    port = await manager.acquire(LaunchOptions(headless=headless()))
    try:
        crawler = XianyuCrawler(
            port,
            BrowserSessionOptions(cookies=cookies_for("xianyu", cookie)),
        )
        ctx = CrawlContext(task_id="probe-search", meta={"cookie": cookie})
        page = await crawler.open_page(ctx)
        try:
            await page.goto(SEARCH_URL, params={"q": query})
            await page.raw.wait_for_timeout(3000)
            print(json.dumps(await page.raw.evaluate(_DIAG_JS), ensure_ascii=False, indent=1))
        finally:
            await crawler.close_page(page)
    finally:
        await manager.release(port)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv[1] if len(sys.argv) > 1 else "露营椅")))
