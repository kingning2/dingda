"""二次探测：商品详情页等待时间线 + class 片段全量。

用法：
    cd server
    .venv\\Scripts\\python.exe scripts/probe_xianyu_detail_dom_wait.py --item-id 1027680267393
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from browser.adapters.camoufox import CamoufoxAdapter  # noqa: E402
from contracts.browser_port import LaunchOptions  # noqa: E402
from channels.cookie_header import parse_cookie_header  # noqa: E402
from channels.xianyu.cookies import to_browser_cookies  # noqa: E402
from infrastructure.db import accounts as account_repo  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dingda.probe.xianyu_detail_wait")
OUT_DIR = _ROOT / "tmp" / "xianyu_detail_dom_probe"
ITEM_URL = "https://www.goofish.com/item"

DUMP_JS = r"""
() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const classes = new Set();
  for (const el of document.querySelectorAll('[class]')) {
    for (const c of el.classList) {
      const frag = c.replace(/--[a-zA-Z0-9_-]{4,}$/, '');
      if (/item|detail|desc|price|title|seller|want|browse|gallery|sku|main|nick|user|area|label|buy|meta|info|content|notLogin|login|wantCnt|collect|original|value|num|photo|carousel|swiper/i.test(frag)) {
        classes.add(c);
      }
    }
  }
  const anchors = [];
  for (const el of document.querySelectorAll('*')) {
    const own = clean(el.childNodes.length ? Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('') : '');
    const t = own || clean(el.textContent || '');
    if (!t || t.length > 28) continue;
    if (/想要|浏览|收藏|成色|品牌|分类|人想要|次浏览/.test(t)) {
      anchors.push({
        text: t.slice(0, 40),
        classes: Array.from(el.classList || []).slice(0, 6),
        parent: Array.from((el.parentElement && el.parentElement.classList) || []).slice(0, 6),
        tag: el.tagName.toLowerCase(),
      });
    }
    if (anchors.length > 40) break;
  }
  const blocks = [];
  for (const el of document.querySelectorAll('div, p, span, pre')) {
    const cn = (el.className || '').toString();
    if (cn.includes('feeds') || cn.includes('search')) continue;
    const t = clean(el.innerText || '');
    if (t.length < 50 || t.length > 2500) continue;
    if (el.children.length > 12) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 120 || r.height < 24) continue;
    blocks.push({
      len: t.length,
      text: t.slice(0, 200),
      classes: Array.from(el.classList || []).slice(0, 6),
      y: Math.round(r.top),
    });
  }
  blocks.sort((a, b) => b.len - a.len);

  // 详情区常见根：排除 feeds 后的大图
  const imgs = [];
  for (const img of document.querySelectorAll('img')) {
    const cn = (img.className || '').toString();
    if (cn.includes('feeds')) continue;
    const r = img.getBoundingClientRect();
    if (r.width < 120 || r.height < 120) continue;
    const src = img.currentSrc || img.src || '';
    if (!src || src.startsWith('data:')) continue;
    imgs.push({
      w: Math.round(r.width),
      h: Math.round(r.height),
      classes: Array.from(img.classList || []).slice(0, 6),
      src: src.slice(0, 160),
      y: Math.round(r.top),
    });
  }
  imgs.sort((a, b) => (b.w * b.h) - (a.w * a.h));

  return {
    url: location.href,
    docTitle: document.title,
    preview: clean((document.body && document.body.innerText) || '').slice(0, 350),
    classNames: Array.from(classes).sort().slice(0, 200),
    anchors: anchors.slice(0, 35),
    longBlocks: blocks.slice(0, 12),
    images: imgs.slice(0, 10),
    feedCount: document.querySelectorAll('[class*="feeds"]').length,
    itemLinkCount: document.querySelectorAll('a[href*="/item?id="]').length,
    hasLibMtop: !!(window.lib && window.lib.mtop && window.lib.mtop.request),
  };
}
"""


def _cookie() -> str:
    rows = account_repo.list_accounts(platform="xianyu")
    for row in rows:
        if row.auth_valid and (row.cookie or "").strip():
            return row.cookie.strip()
    for row in rows:
        if (row.cookie or "").strip():
            return row.cookie.strip()
    raise SystemExit("no xianyu cookie")


async def run(*, item_id: str, headless: bool) -> dict[str, Any]:
    adapter = CamoufoxAdapter()
    await adapter.launch(LaunchOptions(headless=headless))
    page = await adapter.open(
        cookies=to_browser_cookies(parse_cookie_header(_cookie())),
        default_domain=".goofish.com",
    )
    raw = page.raw
    url = f"{ITEM_URL}?{urlencode({'id': item_id})}"
    logger.info("goto %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout_ms=45_000)
    timeline: list[dict[str, Any]] = []
    waits = [2, 3, 4, 5]
    elapsed = 0
    try:
        for w in waits:
            await raw.wait_for_timeout(w * 1000)
            elapsed += w
            dump = await raw.evaluate(DUMP_JS)
            if not isinstance(dump, dict):
                continue
            row = {"after_s": elapsed, **dump}
            timeline.append(row)
            logger.info(
                "t=%ss title=%s feeds=%s mtop=%s classes=%s",
                elapsed,
                str(dump.get("docTitle") or "")[:40],
                dump.get("feedCount"),
                dump.get("hasLibMtop"),
                len(dump.get("classNames") or []),
            )
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=OUT_DIR / "03_detail_wait.jpg", image_type="jpeg", quality=55)
    finally:
        await page.close()
        await adapter.close()

    out = {"item_id": item_id, "timeline": timeline}
    (OUT_DIR / "dump_timeline.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2)[:400_000],
        encoding="utf-8",
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    out = asyncio.run(run(item_id=args.item_id, headless=not args.headed))
    last = (out.get("timeline") or [{}])[-1]
    print("url", last.get("url"))
    print("classNames", json.dumps(last.get("classNames") or [], ensure_ascii=False)[:2000])
    print("anchors", json.dumps(last.get("anchors") or [], ensure_ascii=False)[:2000])
    print("longBlocks", json.dumps(last.get("longBlocks") or [], ensure_ascii=False)[:2000])
    print("images", json.dumps(last.get("images") or [], ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
