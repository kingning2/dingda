"""选品 Tool：compare（1688 同款比价）。

职责：
    契约与执行同文件；经 crawler/sources/ali1688/compare，不经 Browser。

设计说明：
    - 仅 ali1688；image 与 url 二选一
    - 输出带 compare_label 的代表款

使用示例：
    out = await run_compare(CompareInput(image="https://img.alicdn.com/..."))
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, model_validator

from src.crawler.sources.ali1688.compare import compare_products
from src.shared.errors import AppError

logger = logging.getLogger("dingda.tools.compare")

TOOL_NAME = "compare"
TOOL_DESCRIPTION = (
    "1688 同款比价：根据商品图片或链接找同款，"
    "自动选出销量最高、价格最低、综合最优（严选）代表款。"
    "仅支持 ali1688；不要用于闲鱼/小红书。"
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
    query: str | None = Field(
        default=None,
        description="可选附加关键词（规格、品类等）。",
    )
    limit: int = Field(default=3, ge=1, le=10, description="对比代表款数量，默认 3。")
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
        if not self.image and not self.url:
            raise ValueError("比价需要提供 image 或 url")
        return self


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


class CompareOutput(BaseModel):
    """比价出参。"""

    ok: bool = True
    source_image: str | None = None
    source_url: str | None = None
    total_candidates: int = 0
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
            limit=inp.limit,
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
            )
            for item in result.items
        ]
        logger.info("tool done name=compare count=%s", len(rows))
        return CompareOutput(
            ok=True,
            source_image=result.source_image,
            source_url=result.source_url,
            total_candidates=result.total_candidates,
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
