"""1688 同款比价选品。

职责：
    以图或链接搜同款，按销量最高 / 价格最低 / 严选最优各选一款去重。
    供 tools.compare 调用；不经 Browser。

设计说明：
    - 候选固定拉 20 条再选 TOP
    - 标签写入 CrawlItem.raw["_compare_label"]

使用示例：
    out = await compare_products(image="https://...", limit=3)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.crawler.core.types import CrawlContext, CrawlItem
from src.crawler.sources.ali1688.crawler import Ali1688Crawler
from src.crawler.sources.ali1688.link import resolve_image_from_link
from src.shared.errors import AppError

logger = logging.getLogger("dingda.crawler.ali1688.compare")

_CANDIDATE_LIMIT = 20


@dataclass(frozen=True)
class CompareResult:
    """比价产出。"""

    items: list[CrawlItem] = field(default_factory=list)
    source_image: str = ""
    source_url: str | None = None
    total_candidates: int = 0


async def compare_products(
    *,
    image: str | None = None,
    url: str | None = None,
    query: str | None = None,
    limit: int = 3,
    sort_type: str | None = None,
    score_level: str = "high",
    purchase_amount: int = 1,
    tags: str | None = "4306497",
    ic_tags: str | None = None,
) -> CompareResult:
    """图或链接找同款并选出比价代表款。"""
    if not image and not url:
        raise AppError(
            "crawler.ali1688_compare",
            "比价需要提供 image 或 url",
            status_code=400,
        )

    source_url: str | None = None
    source_image = image
    if url and not image:
        source_image, source_url = resolve_image_from_link(url)

    assert source_image is not None

    meta: dict[str, Any] = {
        "mode": "image",
        "image": source_image,
        "limit": _CANDIDATE_LIMIT,
        "score_level": score_level,
        "purchase_amount": purchase_amount,
    }
    if sort_type:
        meta["sort_type"] = sort_type
    if tags is not None:
        meta["tags"] = tags
    if ic_tags:
        meta["ic_tags"] = ic_tags

    task_id = f"compare-{uuid.uuid4().hex[:12]}"
    logger.info(
        "compare start has_image=%s url=%s limit=%s task=%s",
        bool(source_image),
        source_url or url,
        limit,
        task_id,
    )

    crawler = Ali1688Crawler()
    result = await crawler.search(
        CrawlContext(task_id=task_id, meta=meta),
        (query or "").strip(),
    )

    valid = [item for item in result.items if item.title or item.url]
    selected = select_top(valid, limit=limit)
    logger.info(
        "compare done candidates=%s selected=%s",
        len(valid),
        len(selected),
    )
    return CompareResult(
        items=selected,
        source_image=source_image,
        source_url=source_url,
        total_candidates=len(valid),
    )


def select_top(products: list[CrawlItem], limit: int = 3) -> list[CrawlItem]:
    """销量最高 / 价格最低 / 严选最优各一，去重合并标签。"""
    if not products:
        return []

    winners: list[tuple[CrawlItem, str]] = []

    by_sales = sorted(
        products,
        key=lambda p: int(p.raw.get("sold_count") or 0),
        reverse=True,
    )
    if by_sales:
        winners.append((by_sales[0], "销量最高"))

    priced = [p for p in products if p.price is not None]
    if priced:
        by_price = sorted(priced, key=lambda p: float(p.price or 0))
        winners.append((by_price[0], "价格最低"))

    by_yx = sorted(
        products,
        key=lambda p: float(p.raw.get("yx_index") or 0),
        reverse=True,
    )
    if by_yx:
        winners.append((by_yx[0], "综合最优"))

    label_map: dict[str, list[str]] = {}
    ordered: list[CrawlItem] = []
    for product, label in winners:
        pid = product.item_id
        if pid in label_map:
            label_map[pid].append(label)
        else:
            label_map[pid] = [label]
            ordered.append(product)

    out: list[CrawlItem] = []
    for product in ordered[:limit]:
        labels = label_map.get(product.item_id, ["推荐"])
        raw = dict(product.raw)
        raw["_compare_label"] = " 且 ".join(labels)
        out.append(
            CrawlItem(
                item_id=product.item_id,
                title=product.title,
                url=product.url,
                price=product.price,
                raw=raw,
            )
        )
    return out
