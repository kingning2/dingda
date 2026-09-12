"""选品 Tool：compare（1688 同款比价）。

职责：
    契约与执行同文件；经 crawler/sources/ali1688/compare，不经 Browser。

设计说明：
    - 仅 ali1688；image / url / source.image_url 至少一个
    - 默认两轮找货，输出来源商品、代表款与推荐依据

使用示例：
    out = await run_compare(
        CompareInput(
            image="https://img.alicdn.com/...",
            source={"platform": "xianyu", "title": "露营椅", "price": "89"},
        )
    )
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, model_validator

from crawler.sources.ali1688.compare import compare_products
from core.errors import AppError

logger = logging.getLogger("dingda.tools.compare")

TOOL_NAME = "compare"
TOOL_DESCRIPTION = (
    "1688 同款比价：根据来源商品图片、链接或 source 元数据找同款，"
    "默认两轮扩展候选，输出价格、销量、供应商、评分等对比数据和推荐理由。"
    "应把前序 search/product 得到的来源商品作为 source 传入。"
    "仅查询 ali1688；不要用于直接爬闲鱼/小红书。"
)
DEFAULT_TIMEOUT_S = 90.0


class CompareInput(BaseModel):
    """比价入参。"""

    image: str | None = Field(
        default=None,
        description="商品图片本地路径或 URL。与 url 二选一。",
    )
    url: str | None = Field(
        default=None,
        description="商品链接或 ID（1688/淘宝/天猫）。与 image 二选一。",
    )
    source: dict[str, Any] | None = Field(
        default=None,
        description=(
            "来源商品 JSON，建议传 item_id/title/platform/url/price/seller/image_url。"
            "用于解释为何拿这个 1688 商品做对比。"
        ),
    )
    query: str | None = Field(
        default=None,
        description="可选附加关键词（规格、品类等）。",
    )
    limit: int = Field(default=3, ge=1, le=10, description="对比代表款数量，默认 3。")
    rounds: int = Field(
        default=2,
        ge=1,
        le=3,
        description="找货轮次；首轮以图/链接，后续轮用高相似标题扩词。",
    )
    sort: str | None = Field(
        default=None,
        description="候选排序：price_asc / price_desc / sold_desc / yx_desc。",
    )
    score_level: str = Field(default="high", description="相关性：high / medium / low。")
    purchase_amount: int = Field(default=1, ge=1, description="采购件数。")
    tags: str | None = Field(default="4306497", description="TC 品池标签。")
    ic_tags: str | None = Field(default=None, description="IC 品池标签。")

    @model_validator(mode="after")
    def _require_image_or_url(self) -> CompareInput:
        source_image = (self.source or {}).get("image_url") or (self.source or {}).get("image")
        if not self.image and not self.url and not source_image:
            raise ValueError("比价需要提供 image、url 或 source.image_url")
        return self


class CompareSourceItem(BaseModel):
    """比价来源商品。"""

    item_id: str = ""
    title: str = ""
    platform: str = ""
    url: str = ""
    image_url: str = ""
    price: str | None = None
    seller: str | None = None


class CompareItem(BaseModel):
    """比价单条。"""

    item_id: str
    title: str
    url: str
    price: str | None = None
    compare_label: str | None = None
    supplier: str | None = None
    sold_count: int | None = None
    yx_index: float | None = None
    image_url: str | None = None
    similarity_score: float | None = None
    merchant_rating: float | None = None
    repurchase_rate: float | None = None
    stock_amount: int | None = None
    quantity_begin: int | None = None
    unit: str | None = None
    compare_reasons: list[str] = Field(default_factory=list)
    compare_score: float | None = None
    round: int | None = None
    search_query: str | None = None
    search_mode: str | None = None


class CompareOutput(BaseModel):
    """比价出参。"""

    ok: bool = True
    kind: str = "price_compare"
    platform: str = "ali1688"
    source_image: str | None = None
    source_url: str | None = None
    source: CompareSourceItem = Field(default_factory=CompareSourceItem)
    total_candidates: int = 0
    rounds: int = 1
    queries: list[str] = Field(default_factory=list)
    items: list[CompareItem] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


async def run_compare(inp: CompareInput) -> CompareOutput:
    """执行 1688 同款比价。"""
    logger.info(
        "tool start name=compare has_image=%s has_url=%s limit=%s",
        bool(inp.image),
        bool(inp.url),
        inp.limit,
    )
    try:
        result = await compare_products(
            image=inp.image,
            url=inp.url,
            query=inp.query,
            source_item=inp.source,
            limit=inp.limit,
            rounds=inp.rounds,
            sort_type=inp.sort,
            score_level=inp.score_level,
            purchase_amount=inp.purchase_amount,
            tags=inp.tags,
            ic_tags=inp.ic_tags,
        )
        rows = [
            CompareItem(
                item_id=item.item_id,
                title=item.title,
                url=item.url,
                price=item.price,
                compare_label=str(item.raw.get("_compare_label") or "") or None,
                supplier=str(item.raw.get("supplier") or "") or None,
                sold_count=_as_int(item.raw.get("sold_count")),
                yx_index=_as_float(item.raw.get("yx_index")),
                image_url=str(item.raw.get("image_url") or "") or None,
                similarity_score=_as_float(item.raw.get("similarity_score")),
                merchant_rating=_as_float(item.raw.get("merchant_rating")),
                repurchase_rate=_as_float(item.raw.get("repurchase_rate")),
                stock_amount=_as_int(item.raw.get("stock_amount")),
                quantity_begin=_as_int(item.raw.get("quantity_begin")),
                unit=str(item.raw.get("unit") or "") or None,
                compare_reasons=[
                    str(reason)
                    for reason in item.raw.get("_compare_reasons", [])
                    if str(reason).strip()
                ],
                compare_score=_as_float(item.raw.get("_compare_score")),
                round=_as_int(item.raw.get("_compare_round")),
                search_query=str(item.raw.get("_compare_query") or "") or None,
                search_mode=str(item.raw.get("_compare_mode") or "") or None,
            )
            for item in result.items
        ]
        logger.info("tool done name=compare count=%s", len(rows))
        return CompareOutput(
            ok=True,
            source=CompareSourceItem(
                item_id=result.source.item_id,
                title=result.source.title,
                platform=result.source.platform,
                url=result.source.url,
                image_url=result.source.image_url,
                price=result.source.price,
                seller=result.source.seller,
            ),
            source_image=result.source_image,
            source_url=result.source_url,
            total_candidates=result.total_candidates,
            rounds=result.rounds,
            queries=result.queries,
            items=rows,
        )
    except AppError as exc:
        logger.warning("tool failed name=compare code=%s", exc.code)
        return CompareOutput(ok=False, error_code=exc.code, message=exc.message)
    except Exception as exc:
        logger.exception("tool failed name=compare")
        return CompareOutput(ok=False, error_code="tool.failed", message=str(exc))


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
