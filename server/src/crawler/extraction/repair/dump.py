"""精简 DOM 树 dump（经 BrowserPort.evaluate）。

职责：
    在主容器内采集 tag/class/text/children，供 AI 修选择器用。
    排除 feeds 等噪音节点。
"""

from __future__ import annotations

import logging
from typing import Any

from src.browser.port import Page

logger = logging.getLogger("dingda.crawler.repair.dump")

DUMP_JS = r"""
(opts) => {
  const roots = (opts && opts.roots) || ['body'];
  const maxDepth = Number((opts && opts.maxDepth) || 6);
  const maxChildren = Number((opts && opts.maxChildren) || 12);
  const maxText = Number((opts && opts.maxText) || 80);
  const excludeRe = /feeds-item|item-feeds|footer-item|slick-cloned/i;
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim();

  const dumpEl = (el, depth) => {
    if (!el || depth > maxDepth) return null;
    const cn = (el.className || '').toString();
    if (excludeRe.test(cn)) return null;
    const classes = Array.from(el.classList || []).slice(0, 8);
    const text = clean(el.childNodes.length ? Array.from(el.childNodes)
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent)
      .join('') : (el.innerText || '')).slice(0, maxText);
    const kids = [];
    for (const child of Array.from(el.children || []).slice(0, maxChildren)) {
      const row = dumpEl(child, depth + 1);
      if (row) kids.push(row);
    }
    return {
      tag: (el.tagName || '').toLowerCase(),
      classes,
      text,
      kids,
    };
  };

  const trees = [];
  for (const sel of roots) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const node = dumpEl(el, 0);
    if (node) trees.push({ root: sel, node });
  }
  return {
    url: location.href || '',
    title: document.title || '',
    trees,
    preview: clean((document.body && document.body.innerText) || '').slice(0, 240),
  };
}
"""


async def dump_dom_tree(
    page: Page,
    *,
    roots: list[str],
    max_depth: int = 6,
) -> dict[str, Any]:
    """evaluate 精简树；失败返回空结构。"""
    try:
        raw = await page.evaluate(
            DUMP_JS,
            {"roots": roots or ["body"], "maxDepth": max_depth},
        )
    except Exception:  # noqa: BLE001
        logger.exception("dom dump failed")
        return {"url": getattr(page, "url", ""), "trees": [], "preview": ""}
    return raw if isinstance(raw, dict) else {"url": getattr(page, "url", ""), "trees": []}
