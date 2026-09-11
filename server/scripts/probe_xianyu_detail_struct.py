"""针对详情主信息区：dump 关键节点文案（过滑块后）。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.browser.adapters.camoufox import CamoufoxAdapter
from src.browser.port import LaunchOptions
from src.channels.cookie_header import parse_cookie_header
from src.channels.xianyu.cookies import to_browser_cookies
from src.channels.xianyu.slider import clear_risk_cookies, try_solve_slider
from src.infrastructure.db import accounts as account_repo

OUT = _ROOT / "tmp" / "xianyu_detail_dom_probe"
ITEM_ID = "1027680267393"

STRUCT_JS = r"""
() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const dump = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const kids = Array.from(el.children || []).map((c) => ({
      tag: c.tagName.toLowerCase(),
      classes: Array.from(c.classList || []).slice(0, 6),
      text: clean(c.innerText || '').slice(0, 160),
      childCount: c.children.length,
    }));
    return {
      classes: Array.from(el.classList || []).slice(0, 8),
      text: clean(el.innerText || '').slice(0, 300),
      kids,
    };
  };
  const nick = document.querySelector('[class*="item-user-info-nick"]');
  const intro = document.querySelector('[class*="item-user-info-intro"]');
  const labels = Array.from(document.querySelectorAll('[class*="item-main-info"] [class*="labels"]')).map((el) => clean(el.innerText));
  return {
    user_nick: nick ? clean(nick.innerText) : '',
    user_nick_classes: nick ? Array.from(nick.classList) : [],
    user_intro: intro ? clean(intro.innerText) : '',
    info: dump('[class*="item-main-info"]'),
    desc: dump('[class*="item-main-info"] [class*="desc"]'),
    notLogin: dump('[class*="item-main-info"] [class*="notLoginContainer"]'),
    main: dump('[class*="item-main-info"] [class*="main--"], [class*="item-main-info"] .main--Nu33bWl6, [class*="item-main-info"] [class^="main"]'),
    want: dump('[class*="item-main-info"] [class*="want"]'),
    price: dump('[class*="item-main-info"] [class*="price"]'),
    value: dump('[class*="item-main-info"] [class*="value"]'),
    labels,
    imgs: Array.from(document.querySelectorAll('[class*="item-main-window"] img, [class*="carouselItem"] img'))
      .slice(0, 6)
      .map((img) => ({
        src: (img.currentSrc || img.src || '').slice(0, 120),
        classes: Array.from(img.classList || []).slice(0, 4),
        w: Math.round(img.getBoundingClientRect().width),
      })),
  };
}
"""


async def main() -> None:
    cookie = next(
        (r.cookie.strip() for r in account_repo.list_accounts(platform="xianyu") if (r.cookie or "").strip()),
        "",
    )
    if not cookie:
        raise SystemExit("no cookie")
    adapter = CamoufoxAdapter()
    await adapter.launch(LaunchOptions(headless=True))
    page = await adapter.open(
        cookies=to_browser_cookies(parse_cookie_header(cookie)),
        default_domain=".goofish.com",
    )
    raw = page.raw
    url = f"https://www.goofish.com/item?{urlencode({'id': ITEM_ID})}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout_ms=40_000)
        await raw.wait_for_timeout(2000)
        ctx = page.context
        await clear_risk_cookies(ctx)
        ok, detail = await try_solve_slider(raw, ctx, max_retries=3, prefer_page_mouse=True)
        print("slider", ok, detail)
        await page.goto(url, wait_until="domcontentloaded", timeout_ms=40_000)
        await raw.wait_for_timeout(4000)
        data = await raw.evaluate(STRUCT_JS)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "struct.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote struct.json")
    finally:
        await page.close()
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())
