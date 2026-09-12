"""1688 官方找货 Crawler Source。

职责：
    实现 ApiCrawler：文本 / 以图 / 链接找同款，经 channels.ali1688 调网关。
    标准化为 CrawlItem；不经 Browser。

设计说明：
    - platform：ali1688
    - mode 由 ctx.meta.mode 指定：text | image | link（默认 text）
    - 调用方：tools.search / tools.compare、crawler/registry

使用示例：
    crawler = Ali1688Crawler()
    result = await crawler.search(ctx, "黑色卫衣")
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from channels.ali1688.client import find_product
from crawler.core.base import ApiCrawler
from crawler.core.types import CrawlContext, CrawlResult
from crawler.sources.ali1688.extractor import items_from_api
from crawler.sources.ali1688.image import preprocess_image
from crawler.sources.ali1688.link import resolve_image_from_link
from core.errors import AppError

logger = logging.getLogger("dingda.crawler.ali1688")

DEFAULT_TAGS = "4306497"
MAX_LIMIT = 100


class Ali1688Crawler(ApiCrawler):
    """1688 插头：官方 find.product，无浏览器。"""

    platform = "ali1688"

    async def search(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """按 meta.mode 执行文本 / 图片 / 链接搜品。"""
        mode = str(ctx.meta.get("mode") or "text").strip().lower()
        limit = _normalize_limit(ctx.meta.get("limit", 20))
        logger.info(
            "search start mode=%s query=%s limit=%s task=%s",
            mode,
            query,
            limit,
            ctx.task_id,
        )

        if mode == "image":
            body = self._body_from_image(ctx, limit, extra_query=query or None)
        elif mode == "link":
            body = self._body_from_link(ctx, limit)
        else:
            body = self._body_from_text(query, limit, ctx.meta)

        rows = find_product(body)
        items = items_from_api(rows)
        logger.info("search done mode=%s count=%s", mode, len(items))
        return CrawlResult(items=items)

    def _body_from_text(
        self,
        query: str,
        limit: int,
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        """文本搜请求体。"""
        q = (query or "").strip()
        if not q:
            raise AppError("crawler.ali1688_query", "文本搜索需要 query", status_code=400)
        body = _base_request(limit, meta)
        body["query"] = q
        return body

    def _body_from_image(
        self,
        ctx: CrawlContext,
        limit: int,
        *,
        extra_query: str | None = None,
    ) -> dict[str, Any]:
        """以图搜请求体。"""
        image = str(ctx.meta.get("image") or "").strip()
        if not image:
            raise AppError("crawler.ali1688_image", "图片搜索需要 image", status_code=400)

        img_info = preprocess_image(image)
        body = _base_request(limit, ctx.meta)
        body["imgBase64"] = ""
        body["imageUrl"] = None

        converted_path: str | None = None
        try:
            if img_info.get("type") == "url":
                body["imageUrl"] = img_info.get("url")
            else:
                path = str(img_info.get("path") or "")
                if not path or not os.path.exists(path):
                    raise AppError("crawler.ali1688_image", "图片路径无效", status_code=400)
                if img_info.get("converted"):
                    converted_path = path
                with open(path, "rb") as fh:
                    body["imgBase64"] = base64.b64encode(fh.read()).decode("utf-8")

            if extra_query and extra_query.strip():
                body["query"] = extra_query.strip()
            return body
        finally:
            if converted_path:
                try:
                    os.unlink(converted_path)
                except OSError:
                    pass

    def _body_from_link(self, ctx: CrawlContext, limit: int) -> dict[str, Any]:
        """链接找同款：抽主图后以图搜。"""
        url = str(ctx.meta.get("url") or "").strip()
        if not url:
            raise AppError("crawler.ali1688_link", "链接搜索需要 url", status_code=400)
        image_url, _canonical = resolve_image_from_link(url)
        body = _base_request(limit, ctx.meta)
        body["imgBase64"] = ""
        body["imageUrl"] = image_url
        return body


def _base_request(limit: int, meta: dict[str, Any]) -> dict[str, Any]:
    """公共筛选项。"""
    body: dict[str, Any] = {
        "pageSize": limit,
        "purchaseAmount": int(meta.get("purchase_amount") or 1),
    }
    sort_type = meta.get("sort_type") or meta.get("sort")
    if sort_type:
        body["sortType"] = str(sort_type)
    score_level = meta.get("score_level")
    if score_level:
        body["scoreLevel"] = str(score_level)
    else:
        body["scoreLevel"] = "high"

    tags = meta.get("tags")
    if tags is None:
        tags = DEFAULT_TAGS
    if tags:
        body["tags"] = str(tags)
    ic_tags = meta.get("ic_tags")
    if ic_tags:
        body["icTags"] = str(ic_tags)
    return body


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 20
    return min(MAX_LIMIT, max(1, n))
