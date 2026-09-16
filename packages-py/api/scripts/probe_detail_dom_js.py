"""探针：用本地构造的详情 DOM 离线跑 DETAIL_DOM_JS。

职责：
    不联网、不过风控，纯验证 DOM 兜底抽取逻辑：
    页面 ``<title>``、多个 ``[class*="desc"]`` 候选（服务保障文案 vs 真实描述）、
    区间价，各字段是否取对。

设计说明：
    - 闲鱼详情页里 ``[class*="desc"]`` 会同时命中「满足条件时，买家可退货…」这种
      服务保障 div 和真正的 ``span.desc``；querySelector 取到的是靠前的那个，
      于是标题被抽成保障文案。本探针把这个真实结构固化下来防回归。
    - 真实站点被风控封着时（channel.risk），这是唯一还能验这条逻辑的办法。

使用示例：
    python -m api.scripts.probe_detail_dom_js
"""

from __future__ import annotations

import asyncio
import json

from browser.manager import get_browser_manager
from contracts.browser_port import LaunchOptions
from crawler.core.base import BrowserSessionOptions
from crawler.core.types import CrawlContext
from crawler.sources.xianyu.crawler import XianyuCrawler
from crawler.sources.xianyu.extractor import DETAIL_DOM_JS, detail_dom_arg

_ITEM_ID = "1067057484474"
_REAL_TITLE = "【8.99元一把包邮】户外折叠椅月亮椅桌子露营装备全套便携野餐桌椅套装钓鱼凳子椅子"
_REAL_DESC = (
    _REAL_TITLE
    + "\n全新户外折叠椅月亮椅，便携户外舒适椅，多场景适用，舒适坐感，三面环抱柔软舒适，"
    "加厚碳钢材质，稳固耐用，牛津布材质，可折叠收纳，侧边收纳设计。"
)

# 真实站点结构：保障文案的 div.desc 在文档里排在 span.desc 之前。
_FIXTURE = f"""<!doctype html>
<html><head><title>{_REAL_TITLE}_闲鱼</title></head>
<body>
  <div class="item-main-container--x">
    <div class="item-main-info--y">
      <div class="price--a windows--b"><span>8.9</span><span> - </span><span>15.5</span></div>
      <div class="desc--z">满足条件时，买家可退货且运费由卖家承担</div>
      <div class="want--w"><div>2607人想要</div><div>3万浏览</div></div>
      <span class="desc--z"><span>{_REAL_DESC}</span></span>
    </div>
    <div class="item-user-info-nick--n">美女然然吖</div>
    <div class="item-user-info-intro--i">常州 刚刚来过</div>
    <div class="item-main-window--m"><img src="https://img.test/a.jpg"></div>
  </div>
</body></html>"""


async def _main() -> int:
    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=True))
    try:
        crawler = XianyuCrawler(port, BrowserSessionOptions())
        page = await crawler.open_page(CrawlContext(task_id="probe-dom"))
        try:
            await page.raw.set_content(_FIXTURE)
            payload = await page.raw.evaluate(DETAIL_DOM_JS, detail_dom_arg(_ITEM_ID))
        finally:
            await crawler.close_page(page)
    finally:
        await manager.release(port)

    if not isinstance(payload, dict):
        print("payload not dict:", payload)
        return 1
    print(json.dumps(
        {
            "title": payload.get("title"),
            "price": payload.get("price"),
            "seller_name": payload.get("seller_name"),
            "location": payload.get("location"),
            "want_count": payload.get("want_count"),
            "browse_count": payload.get("browse_count"),
            "desc_len": len(str(payload.get("description") or "")),
            "error": payload.get("error"),
        },
        ensure_ascii=False,
        indent=1,
    ))

    # price 带 ¥ 前缀且保留区间原文：区间→起价的归一化在 item_from_view 里做
    # （见 extractor.normalize_price），本探针只验 DOM 抽取这一段。
    ok = (
        payload.get("title") == _REAL_TITLE
        and payload.get("price") == "¥8.9 - 15.5"
        and str(payload.get("description") or "").startswith(_REAL_TITLE)
        and payload.get("seller_name") == "美女然然吖"
    )
    print("RESULT:", "OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
