"""Crawler 路由域。

职责：
    聚合 crawler 域各端点挂到 ``/v1/crawler``；每端点一个文件。
    把前端搜品 / 详情请求接到 tools.search / tools.product，
    /search/live、/product/live 用 SSE 推浏览器截图帧。

设计说明：
    - POST /v1/crawler/search        一次性结果
    - POST /v1/crawler/search/live   SSE：frame / result / error / done
    - POST /v1/crawler/product       单品详情
    - POST /v1/crawler/product/live  SSE：frame / result / error / done
    - 本层不写平台解析或 Playwright
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.crawler import product, product_live, search, search_live

router = APIRouter(prefix="/v1/crawler", tags=["crawler"])
router.include_router(search.router)
router.include_router(search_live.router)
router.include_router(product.router)
router.include_router(product_live.router)
