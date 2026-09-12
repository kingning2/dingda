"""探测：闲鱼商品详情页 DOM 选择器。

职责：
    用账号库 cookie 打开 goofish 商品页，启发式扫描标题/价格/描述/卖家/想要数/
    浏览量/主图等候选节点，写出候选 CSS 与样本文本，供 ``extract.json`` detail_dom 固化。

设计说明：
    - 独立脚本，不改产品代码；默认有头，方便对照页面
    - 探测方法：关键词 class 匹配 + 文案正则（¥ / 想要 / 浏览）+ 可见文本长度打分
    - 不要求账号 connected，只要 auth_valid + cookie

用法：
    cd server
    .venv\\Scripts\\python.exe scripts/probe_xianyu_detail_dom.py
    .venv\\Scripts\\python.exe scripts/probe_xianyu_detail_dom.py --item-id 123 --headless
    .venv\\Scripts\\python.exe scripts/probe_xianyu_detail_dom.py --keyword 键盘
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
from channels.xianyu.slider import clear_risk_cookies, try_solve_slider  # noqa: E402
from infrastructure.db import accounts as account_repo  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("dingda.probe.xianyu_detail_dom")

OUT_DIR = _ROOT / "tmp" / "xianyu_detail_dom_probe"
SEARCH_URL = "https://www.goofish.com/search"
ITEM_URL = "https://www.goofish.com/item"

# 页内探测：限定在 item-main-container，避开右侧/下方 feeds 推荐卡
PROBE_JS = r"""
() => {
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();
  const absUrl = (v) => {
    const s = clean(v);
    if (!s || s.startsWith('data:')) return '';
    if (s.startsWith('//')) return 'https:' + s;
    return s;
  };

  const root =
    document.querySelector('[class*="item-main-container"]')
    || document.querySelector('[class*="item-container"]')
    || document.body;

  const inFeeds = (el) => {
    let cur = el;
    while (cur && cur !== document.body) {
      const cn = (cur.className || '').toString();
      if (/feeds-item|item-feeds|footer-item/.test(cn)) return true;
      cur = cur.parentElement;
    }
    return false;
  };

  const cssPath = (el) => {
    if (!el || el === document.body) return 'body';
    const parts = [];
    let cur = el;
    for (let depth = 0; cur && cur !== document.body && depth < 6; depth++) {
      let part = cur.tagName.toLowerCase();
      const cls = Array.from(cur.classList || []).filter(Boolean);
      const semantic = cls.find((c) =>
        /title|price|desc|seller|want|browse|gallery|main|item|nick|area|avatar|image|pic|detail|carousel|label|original/i.test(c)
      );
      if (semantic) {
        const frag = semantic.replace(/--[a-zA-Z0-9_-]{4,}$/, '').slice(0, 36);
        part += `[class*="${frag}"]`;
        parts.unshift(part);
        break;
      }
      if (cls[0]) part += `.${CSS.escape(cls[0])}`;
      parts.unshift(part);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  };

  const visible = (el) => {
    if (!el) return false;
    const st = window.getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  };

  const scoreClass = (cls, keywords) => {
    const blob = (cls || []).join(' ').toLowerCase();
    let score = 0;
    for (const kw of keywords) {
      if (blob.includes(kw.toLowerCase())) score += 3;
    }
    return score;
  };

  const pickCandidates = (keywords, { minText = 0, maxText = 500, textRe = null, limit = 8 } = {}) => {
    const out = [];
    for (const el of root.querySelectorAll('*')) {
      if (!visible(el) || inFeeds(el)) continue;
      const cls = Array.from(el.classList || []);
      let score = scoreClass(cls, keywords);
      const text = clean(el.innerText || el.textContent || '');
      if (text.length < minText || text.length > maxText) {
        if (score < 3) continue;
      }
      if (textRe && text && textRe.test(text)) score += 4;
      if (score < 3 && !(textRe && text && textRe.test(text))) continue;
      const childSame = Array.from(el.children || []).some(
        (c) => clean(c.innerText || '') === text && text.length > 0
      );
      if (childSame) score -= 1;
      out.push({
        score,
        tag: el.tagName.toLowerCase(),
        classes: cls.slice(0, 8),
        text: text.slice(0, 200),
        selector: cssPath(el),
        classStar: cls
          .filter((c) => keywords.some((k) => c.toLowerCase().includes(k.toLowerCase())))
          .map((c) => {
            const frag = c.replace(/--[a-zA-Z0-9_-]{4,}$/, '').slice(0, 36);
            return `[class*="${frag}"]`;
          }),
      });
    }
    out.sort((a, b) => b.score - a.score);
    const seen = new Set();
    const uniq = [];
    for (const row of out) {
      const key = row.selector + '|' + row.text.slice(0, 40);
      if (seen.has(key)) continue;
      seen.add(key);
      uniq.push(row);
      if (uniq.length >= limit) break;
    }
    return uniq;
  };

  const images = [];
  for (const img of root.querySelectorAll('img')) {
    if (!visible(img) || inFeeds(img)) continue;
    const src = absUrl(img.currentSrc || img.src || img.getAttribute('data-src') || '');
    if (!src) continue;
    const r = img.getBoundingClientRect();
    if (r.width < 80 || r.height < 80) continue;
    images.push({
      src: src.slice(0, 200),
      w: Math.round(r.width),
      h: Math.round(r.height),
      classes: Array.from(img.classList || []).slice(0, 6),
      selector: cssPath(img),
    });
  }
  images.sort((a, b) => b.w * b.h - a.w * a.h);

  const bodyText = clean((document.body && document.body.innerText) || '').slice(0, 2500);
  const rootText = clean(root.innerText || '').slice(0, 1200);
  const login = /请先登录|登录后|扫码登录/.test(bodyText);
  const risk = /验证码|安全验证|异常访问|被挤爆|拖动下方滑块|请按住滑块/.test(bodyText);

  const anchorHits = [];
  for (const el of root.querySelectorAll('*')) {
    if (!visible(el) || inFeeds(el)) continue;
    const t = clean(el.childNodes.length === 1 ? (el.textContent || '') : '');
    if (!t || t.length > 48) continue;
    if (/想要|浏览|收藏|成色|品牌|次浏览|人想要/.test(t)) {
      anchorHits.push({
        text: t,
        classes: Array.from(el.classList || []).slice(0, 6),
        selector: cssPath(el),
        parentClasses: Array.from((el.parentElement && el.parentElement.classList) || []).slice(0, 6),
      });
    }
    if (anchorHits.length >= 25) break;
  }

  const allClasses = new Set();
  for (const el of root.querySelectorAll('[class]')) {
    if (inFeeds(el)) continue;
    for (const c of el.classList) allClasses.add(c);
  }

  return {
    url: location.href || '',
    title: document.title || '',
    root: (root.className || '').toString().slice(0, 80),
    login,
    risk,
    preview: rootText.slice(0, 280),
    body_preview: bodyText.slice(0, 180),
    fields: {
      title: pickCandidates(['title', 'main-title', 'item-title', 'row1-wrap-title'], {
        minText: 4,
        maxText: 160,
        limit: 6,
      }),
      price: pickCandidates(['price', 'sold', 'price-wrap', 'number'], {
        minText: 1,
        maxText: 48,
        textRe: /¥|￥|\d+(\.\d+)?/,
        limit: 8,
      }),
      desc: pickCandidates(['desc', 'detail-desc', 'desc-content', 'item-desc', 'notLogin'], {
        minText: 8,
        maxText: 2500,
        limit: 8,
      }),
      seller: pickCandidates(['item-user-info-nick', 'seller-text', 'nick'], {
        minText: 1,
        maxText: 40,
        limit: 6,
      }),
      want: pickCandidates(['want', 'wantCnt', 'want-count', 'price-desc'], {
        minText: 0,
        maxText: 40,
        textRe: /想要/,
        limit: 6,
      }),
      browse: pickCandidates(['browse', 'view', 'pv', 'meta'], {
        minText: 0,
        maxText: 40,
        textRe: /浏览/,
        limit: 6,
      }),
      location: pickCandidates(['area', 'city', 'location', 'addr', 'intro'], {
        minText: 1,
        maxText: 40,
        limit: 4,
      }),
    },
    images: images.slice(0, 12),
    anchors: anchorHits,
    classNames: Array.from(allClasses).sort().slice(0, 120),
    lib_mtop: !!(window.lib && window.lib.mtop && typeof window.lib.mtop.request === 'function'),
    has_slider: !!document.querySelector('#nc_1_n1z, .nc_iconfont.btn_slide, [class*="baxia-dialog"]'),
  };
}
"""


def _pick_cookie() -> tuple[str, str]:
    rows = account_repo.list_accounts(platform="xianyu")
    for row in rows:
        if row.auth_valid and (row.cookie or "").strip():
            return row.account_id, row.cookie.strip()
    for row in rows:
        if (row.cookie or "").strip():
            return row.account_id, row.cookie.strip()
    raise SystemExit("账号库没有闲鱼 cookie，请先扫码登录")


def _recommend(probe: dict[str, Any]) -> dict[str, str]:
    """从候选里挑每个字段的首选 class* 选择器。"""
    fields = probe.get("fields") if isinstance(probe.get("fields"), dict) else {}
    out: dict[str, str] = {}
    for key, rows in fields.items():
        if not isinstance(rows, list) or not rows:
            continue
        top = rows[0] if isinstance(rows[0], dict) else {}
        stars = top.get("classStar") if isinstance(top.get("classStar"), list) else []
        if stars:
            out[key] = str(stars[0])
            continue
        sel = str(top.get("selector") or "").strip()
        if sel:
            out[key] = sel
    imgs = probe.get("images") if isinstance(probe.get("images"), list) else []
    if imgs and isinstance(imgs[0], dict):
        cls = imgs[0].get("classes") if isinstance(imgs[0].get("classes"), list) else []
        if cls:
            frag = str(cls[0]).split("--")[0][:28]
            out["img"] = f'img[class*="{frag}"]' if frag else "img"
        else:
            out["img"] = "img"
    return out


async def _shot(page: Any, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    await page.screenshot(path=path, image_type="jpeg", quality=55)
    return path


async def _find_item_id_via_search(page: Any, keyword: str) -> str | None:
    """搜索页点第一张商品卡，从 URL 抽 id。"""
    raw = page.raw
    url = f"{SEARCH_URL}?{urlencode({'q': keyword})}"
    logger.info("search goto %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout_ms=40_000)
    await raw.wait_for_timeout(3000)
    await _shot(page, "01_search.jpg")
    href = await raw.evaluate(
        r"""() => {
          const a = document.querySelector('a[href*="/item?id="], a[href*="/item?id%3D"]');
          return a ? (a.href || a.getAttribute('href') || '') : '';
        }"""
    )
    text = str(href or "")
    import re

    m = re.search(r"[?&]id=(\d+)", text)
    if m:
        return m.group(1)
    # 再等一轮懒加载
    await raw.wait_for_timeout(2000)
    href = await raw.evaluate(
        r"""() => {
          const as = Array.from(document.querySelectorAll('a[href*="item"]'));
          for (const a of as) {
            const h = a.href || a.getAttribute('href') || '';
            if (/[?&]id=\d+/.test(h)) return h;
          }
          return '';
        }"""
    )
    m = re.search(r"[?&]id=(\d+)", str(href or ""))
    return m.group(1) if m else None


async def run_probe(
    *,
    item_id: str | None,
    keyword: str,
    headless: bool,
    keep_open_s: float,
) -> dict[str, Any]:
    """打开商品详情并跑 DOM 探测，写 tmp 产物。"""
    account_id, cookie = _pick_cookie()
    cookies = to_browser_cookies(parse_cookie_header(cookie))
    logger.info(
        "account=%s cookie_count=%s headless=%s item_id=%s keyword=%s",
        account_id,
        len(cookies or []),
        headless,
        item_id,
        keyword,
    )

    adapter = CamoufoxAdapter()
    await adapter.launch(LaunchOptions(headless=headless))
    page = await adapter.open(cookies=cookies, default_domain=".goofish.com")
    raw = page.raw
    summary: dict[str, Any] = {
        "account_id": account_id,
        "item_id": item_id,
        "keyword": keyword,
        "probe": None,
        "recommend": {},
        "slider": None,
        "method": [
            "1. 注入账号库 cookie，Camoufox 打开 goofish",
            "2. 无 item_id 时先搜 keyword，从 a[href*=/item?id=] 取首条",
            "3. 打开 /item?id=…；若出现百信滑块则 try_solve_slider（与产品 crawler 同路径）",
            "4. 过滑块后重开详情，等到 [class*=item-main-container] 有实质文案",
            "5. evaluate 只在主容器内扫描，排除 feeds-item / item-feeds（推荐流会污染选择器）",
            "6. 按 class 关键词 + 文案正则打分，输出 [class*=\"语义片段\"]（对抗 CSS Modules 哈希）",
            "7. 大图按可见面积排序；锚点收集「想要/浏览」短文本",
            "8. recommend → 写入 extract.json detail_dom，供 DETAIL_DOM_JS 兜底",
        ],
    }

    try:
        resolved = item_id
        if not resolved:
            resolved = await _find_item_id_via_search(page, keyword)
            summary["item_id"] = resolved
            if not resolved:
                logger.error("搜索未拿到 item_id")
                return summary

        item_url = f"{ITEM_URL}?{urlencode({'id': resolved})}"
        logger.info("detail goto %s", item_url)
        await page.goto(item_url, wait_until="domcontentloaded", timeout_ms=40_000)
        await raw.wait_for_timeout(2500)
        await _shot(page, "02_detail_before_slider.jpg")

        # 详情常被百信滑块挡住；不过滑块只能扫到骨架/feeds
        context = getattr(page, "context", None) or raw.context
        await clear_risk_cookies(context)
        ok, detail = await try_solve_slider(
            raw,
            context,
            max_retries=3,
            prefer_page_mouse=True,
        )
        summary["slider"] = {"ok": ok, "detail": detail}
        logger.info("slider ok=%s detail=%s", ok, detail)
        if ok:
            await page.goto(item_url, wait_until="domcontentloaded", timeout_ms=40_000)
            await raw.wait_for_timeout(3500)
        else:
            await raw.wait_for_timeout(2000)
        await _shot(page, "03_detail_after_slider.jpg")

        # 等主容器出字（过滑块后 SPA 再灌数据）
        for _ in range(20):
            ready = await raw.evaluate(
                r"""() => {
                  const root = document.querySelector('[class*="item-main-container"]');
                  const t = (root && root.innerText || '').replace(/\s+/g, ' ').trim();
                  const risk = /拖动下方滑块|请按住滑块|安全验证/.test(document.body.innerText || '');
                  return { len: t.length, risk, mtop: !!(window.lib && window.lib.mtop) };
                }"""
            )
            logger.info("wait main %s", ready)
            if isinstance(ready, dict) and int(ready.get("len") or 0) > 40 and not ready.get("risk"):
                break
            await raw.wait_for_timeout(500)

        probe = await raw.evaluate(PROBE_JS)
        if not isinstance(probe, dict):
            raise RuntimeError(f"probe 返回非 dict: {type(probe)}")
        summary["probe"] = probe
        summary["recommend"] = _recommend(probe)
        logger.info(
            "probe login=%s risk=%s lib_mtop=%s recommend=%s",
            probe.get("login"),
            probe.get("risk"),
            probe.get("lib_mtop"),
            json.dumps(summary["recommend"], ensure_ascii=False),
        )

        if keep_open_s > 0 and not headless:
            logger.info("保持窗口 %.0fs…", keep_open_s)
            await raw.wait_for_timeout(int(keep_open_s * 1000))
    finally:
        await page.close()
        await adapter.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)[:200_000],
        encoding="utf-8",
    )
    logger.info("摘要已写 %s", OUT_DIR / "summary.json")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="探测闲鱼详情 DOM")
    parser.add_argument("--item-id", default="")
    parser.add_argument("--keyword", default="机械键盘")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-open", type=float, default=6.0)
    args = parser.parse_args()
    summary = asyncio.run(
        run_probe(
            item_id=(args.item_id or "").strip() or None,
            keyword=args.keyword,
            headless=args.headless,
            keep_open_s=0.0 if args.headless else args.keep_open,
        )
    )
    print("\n=== 探测方法 ===")
    for line in summary.get("method") or []:
        print(line)
    print("\n=== recommend（拟写入 extract.json detail_dom）===")
    print(json.dumps(summary.get("recommend") or {}, ensure_ascii=False, indent=2))
    probe = summary.get("probe") or {}
    print(
        f"\nlogin={probe.get('login')} risk={probe.get('risk')} "
        f"lib_mtop={probe.get('lib_mtop')} url={str(probe.get('url') or '')[:100]}"
    )
    print(f"产物目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
