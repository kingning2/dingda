"""1688 同款比价选品。

职责：
    以图或链接搜同款，再做一轮文本扩展，按销量 / 价格 / 严选选出代表款。
    供 tools.compare 调用；不经 Browser。

设计说明：
    - 首轮固定拉 20 条，默认用高相似候选标题再扩一轮
    - 推荐理由写入 CrawlItem.raw，不在这里调用 LLM

使用示例：
    out = await compare_products(image="https://...", source_item=source, limit=3)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import urlparse

from crawler.core.types import CrawlContext, CrawlItem
from crawler.sources.ali1688.crawler import Ali1688Crawler
from crawler.sources.ali1688.link import resolve_image_from_link
from core.errors import AppError

logger = logging.getLogger("dingda.crawler.ali1688.compare")

_CANDIDATE_LIMIT = 20
_DEFAULT_ROUNDS = 2
_MAX_ROUNDS = 3


@dataclass(frozen=True)
class CompareSource:
    """比价来源商品。"""

    item_id: str = ""
    title: str = ""
    platform: str = ""
    url: str = ""
    image_url: str = ""
    price: str | None = None
    seller: str | None = None


@dataclass(frozen=True)
class CompareResult:
    """比价产出。"""

    items: list[CrawlItem] = field(default_factory=list)
    source: CompareSource = field(default_factory=CompareSource)
    source_image: str = ""
    source_url: str | None = None
    total_candidates: int = 0
    rounds: int = 1
    queries: list[str] = field(default_factory=list)


async def compare_products(
    *,
    image: str | None = None,
    url: str | None = None,
    query: str | None = None,
    source_item: dict[str, Any] | None = None,
    limit: int = 3,
    rounds: int = _DEFAULT_ROUNDS,
    sort_type: str | None = None,
    score_level: str = "high",
    purchase_amount: int = 1,
    tags: str | None = "4306497",
    ic_tags: str | None = None,
) -> CompareResult:
    """图或链接找同款，多轮扩展后选出比价代表款。"""
    source_item = source_item or {}
    source_image = (
        (image or "").strip()
        or _clean_text(source_item.get("image_url") or source_item.get("image"))
    )
    source_url = (
        (url or "").strip()
        or _clean_text(source_item.get("url") or source_item.get("product_url"))
        or None
    )
    if not source_image and source_url:
        source_image, source_url = resolve_image_from_link(source_url)
    if not source_image:
        raise AppError(
            "crawler.ali1688_compare",
            "比价需要提供 image、url 或 source.image_url",
            status_code=400,
        )

    source = CompareSource(
        item_id=_clean_text(source_item.get("item_id") or source_item.get("id")),
        title=_clean_text(source_item.get("title")),
        platform=_clean_text(source_item.get("platform")) or _platform_from_url(source_url),
        url=source_url or "",
        image_url=source_image,
        price=_optional_text(source_item.get("price")),
        seller=_optional_text(
            source_item.get("seller") or source_item.get("seller_nick")
        ),
    )

    task_id = f"compare-{uuid.uuid4().hex[:12]}"
    logger.info(
        "compare start has_image=%s url=%s source=%s limit=%s rounds=%s task=%s",
        bool(source_image),
        source_url or url,
        source.item_id or source.platform,
        limit,
        rounds,
        task_id,
    )

    crawler = Ali1688Crawler()
    candidates: dict[str, CrawlItem] = {}
    round_queries: list[str] = []
    rounds_used = 0
    total_rounds = max(1, min(int(rounds), _MAX_ROUNDS))
    for round_index in range(total_rounds):
        if round_index == 0:
            meta = _search_meta(
                mode="image",
                image=source_image,
                sort_type=sort_type,
                score_level=score_level,
                purchase_amount=purchase_amount,
                tags=tags,
                ic_tags=ic_tags,
            )
            round_query = (query or "").strip()
        else:
            seed = _best_similarity(candidates.values())
            if not seed or not seed.title.strip():
                break
            meta = _search_meta(
                mode="text",
                sort_type=sort_type,
                score_level=score_level,
                purchase_amount=purchase_amount,
                tags=tags,
                ic_tags=ic_tags,
            )
            round_query = _query_from_title(seed.title, query)

        result = await crawler.search(
            CrawlContext(task_id=task_id, meta=meta),
            round_query,
        )
        rounds_used += 1
        round_queries.append(round_query or f"[{meta['mode']}]")
        for item in result.items:
            key = item.item_id or item.url
            if not key or key in candidates:
                continue
            candidates[key] = replace(
                item,
                raw={
                    **item.raw,
                    "_compare_round": round_index + 1,
                    "_compare_query": round_query or f"[{meta['mode']}]",
                    "_compare_mode": meta["mode"],
                },
            )
        logger.info(
            "compare round=%s mode=%s count=%s total=%s",
            round_index + 1,
            meta["mode"],
            len(result.items),
            len(candidates),
        )

    valid = [item for item in candidates.values() if item.title or item.url]
    selected = select_top(valid, limit=limit)
    logger.info(
        "compare done candidates=%s selected=%s rounds=%s",
        len(valid),
        len(selected),
        rounds_used,
    )
    return CompareResult(
        items=selected,
        source=source,
        source_image=source_image,
        source_url=source_url,
        total_candidates=len(valid),
        rounds=rounds_used,
        queries=round_queries,
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
    by_price: list[CrawlItem] = []
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

    by_similarity = sorted(
        products,
        key=lambda p: _similarity_unit(p.raw.get("similarity_score")),
        reverse=True,
    )
    if by_similarity and _similarity_unit(by_similarity[0].raw.get("similarity_score")) > 0:
        winners.append((by_similarity[0], "同款相似度最高"))

    label_map: dict[str, list[str]] = {}
    ordered: list[CrawlItem] = []
    for product, label in winners:
        pid = product.item_id
        if pid in label_map:
            label_map[pid].append(label)
        else:
            label_map[pid] = [label]
            ordered.append(product)

    ranked = _rank_products(products)
    out: list[CrawlItem] = []
    for product in ordered[:limit]:
        labels = label_map.get(product.item_id, ["推荐"])
        raw = dict(product.raw)
        raw["_compare_label"] = " 且 ".join(labels)
        raw["_compare_reasons"] = labels
        raw["_compare_score"] = ranked.get(product.item_id)
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


def _search_meta(
    *,
    mode: str,
    image: str | None = None,
    sort_type: str | None = None,
    score_level: str = "high",
    purchase_amount: int = 1,
    tags: str | None = "4306497",
    ic_tags: str | None = None,
) -> dict[str, Any]:
    """组装单轮 1688 找货筛选条件。"""
    meta: dict[str, Any] = {
        "mode": mode,
        "limit": _CANDIDATE_LIMIT,
        "score_level": score_level,
        "purchase_amount": purchase_amount,
    }
    if image:
        meta["image"] = image
    if sort_type:
        meta["sort_type"] = sort_type
    if tags is not None:
        meta["tags"] = tags
    if ic_tags:
        meta["ic_tags"] = ic_tags
    return meta


def _best_similarity(products: Any) -> CrawlItem | None:
    """返回相似度最高的候选，供下一轮文本扩展取词。"""
    rows = list(products)
    if not rows:
        return None
    return max(rows, key=lambda item: _similarity_unit(item.raw.get("similarity_score")))


def _query_from_title(title: str, extra_query: str | None = None) -> str:
    """用高相似标题扩词；用户补充词优先追加。"""
    base = _clean_text(title)[:40]
    extra = _clean_text(extra_query)
    if extra and extra not in base:
        return f"{base} {extra}".strip()
    return base


def _rank_products(products: list[CrawlItem]) -> dict[str, float]:
    """按匹配度、价格、销量、严选指数生成 0~100 综合分。"""
    if not products:
        return {}
    prices = [_as_float(item.price) for item in products]
    valid_prices = [price for price in prices if price and price > 0]
    min_price = min(valid_prices) if valid_prices else None
    max_sales = max((_as_int(item.raw.get("sold_count")) or 0 for item in products), default=0)
    max_yx = max((_as_float(item.raw.get("yx_index")) or 0 for item in products), default=0)

    out: dict[str, float] = {}
    for item in products:
        price = _as_float(item.price)
        price_score = min_price / price if min_price and price and price > 0 else 0.0
        sales_score = (
            (_as_int(item.raw.get("sold_count")) or 0) / max_sales if max_sales else 0.0
        )
        yx_score = (_as_float(item.raw.get("yx_index")) or 0) / max_yx if max_yx else 0.0
        similarity = _similarity_unit(item.raw.get("similarity_score"))
        score = (
            similarity * 35
            + price_score * 25
            + sales_score * 20
            + yx_score * 20
        )
        out[item.item_id] = round(score, 1)
    return out


def _similarity_unit(value: Any) -> float:
    """把 0~1 或 0~100 的相似度统一成 0~1。"""
    score = _as_float(value) or 0.0
    if score > 1:
        score /= 100
    return min(1.0, max(0.0, score))


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _platform_from_url(url: str | None) -> str:
    """从来源链接粗判平台，仅用于界面标签。"""
    host = urlparse(url or "").netloc.lower()
    if "goofish" in host:
        return "xianyu"
    if "xiaohongshu" in host:
        return "xiaohongshu"
    if "1688" in host:
        return "ali1688"
    if "taobao" in host or "tmall" in host:
        return "taobao"
    return "source"
