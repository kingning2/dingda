"""商品条目归一：crawler 的行 → 前端认的一条商品。

职责：
    定义 ``DetailItem``（列表 / 详情 / 直播共用的出参形状）与 ``item_from_row``
    （``CrawlItem`` → ``DetailItem``）。

设计说明：
    - **出参是共用的单一真源**：前端 ``agent-output.ts`` 按一个形状解析商品，
      列表与详情各写一份只会漂移。所以列表也用 ``DetailItem``，只是多数详情字段为空。
    - 字段不做平台分支 —— 有就带，没有就空。平台差异在**怎么取**上（见 tools/crawl.py）。
"""

from __future__ import annotations

from typing import Any

from contracts.watch import SoldState
from crawler.core.types import CrawlItem
from pydantic import BaseModel, Field


class ProductComment(BaseModel):
    """商品留言（闲鱼详情带，其它平台可能为空）。"""

    author: str = Field(description="留言者昵称")
    content: str = Field(description="留言正文")
    time: str | None = Field(default=None, description="时间文案，可能为空")
    reply: str | None = Field(default=None, description="首条回复正文，可能为空")


class DetailItem(BaseModel):
    """一条商品 / 笔记。

    字段名对齐前端 ``CrawlProductItem``：``item_id`` / ``seller_nick`` / ``url`` 这些
    改一个字母，商品面板就会少一条。
    """

    item_id: str = Field(description="商品或笔记 id")
    title: str = Field(description="标题")
    url: str = Field(description="页面链接")
    platform: str = Field(description="平台 id")
    price: str | None = Field(default=None, description="价格，可能为空")
    seller_nick: str | None = Field(default=None, description="卖家/作者昵称，可能为空")
    status: str | None = Field(default=None, description="状态文案原文，可能为空")
    sold_state: str = Field(
        default=SoldState.UNKNOWN,
        description=(
            "售出态（由平台状态文案映射）：unknown / on_sale / sold / delisted / gone。"
            "unknown 表示文案没命中关键词，要看 status 原文判断，不要臆断。"
        ),
    )
    want_count: str | None = Field(default=None, description="想要人数（闲鱼），可能为空")
    browse_count: str | None = Field(default=None, description="浏览量，可能为空")
    image_url: str | None = Field(default=None, description="封面图，可能为空")
    location: str | None = Field(default=None, description="地区，可能为空")
    desc: str | None = Field(default=None, description="正文描述，可能为空")
    comments: list[ProductComment] = Field(
        default_factory=list,
        description="留言列表；无留言或未拉取时为空",
    )
    ocr_text: str | None = Field(default=None, description="图片 OCR 文字，可能为空")
    content_text: str | None = Field(
        default=None,
        description="正文 + 图片 OCR 合并文本（小红书）；读笔记在说什么优先看这个",
    )
    note_type: str | None = Field(default=None, description="笔记类型：normal / video")
    xsec_token: str | None = Field(
        default=None,
        description="搜索下发的 token（小红书）；拉详情必须带回，否则 300031",
    )


def item_from_row(row: CrawlItem, *, platform: str) -> DetailItem:
    """``CrawlItem`` → ``DetailItem``，全字段尽力映射。"""
    raw = row.raw if isinstance(row.raw, dict) else {}
    return DetailItem(
        item_id=row.item_id,
        title=row.title,
        url=row.url,
        platform=platform,
        price=row.price,
        seller_nick=raw_text(raw, "seller_nick"),
        status=raw_text(raw, "status"),
        sold_state=raw_text(raw, "sold_state") or SoldState.UNKNOWN,
        want_count=raw_text(raw, "want_count"),
        browse_count=raw_text(raw, "browse_count"),
        image_url=raw_text(raw, "image_url"),
        location=raw_text(raw, "location"),
        desc=raw_text(raw, "desc"),
        comments=comments_from_raw(raw.get("comments")),
        ocr_text=raw_text(raw, "ocr_text"),
        content_text=raw_text(raw, "content_text"),
        note_type=raw_text(raw, "note_type"),
        xsec_token=raw_text(raw, "xsec_token"),
    )


def comments_from_raw(value: Any) -> list[ProductComment]:
    """``raw.comments`` → ``ProductComment`` 列表；形状不对就返回空。"""
    if not isinstance(value, list):
        return []
    out: list[ProductComment] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        out.append(
            ProductComment(
                author=str(row.get("author") or "").strip() or "匿名",
                content=content,
                time=str(row.get("time") or "").strip() or None,
                reply=str(row.get("reply") or "").strip() or None,
            )
        )
    return out


def raw_text(raw: dict[str, Any], key: str) -> str | None:
    """从 ``CrawlItem.raw`` 取非空字符串（空串与缺字段都归 None）。"""
    value = raw.get(key)
    if value is None:
        return None
    return str(value).strip() or None
