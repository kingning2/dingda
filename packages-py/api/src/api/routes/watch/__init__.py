"""商品监控路由域。

职责：
    聚合 watch 域各端点挂到 ``/v1/watch``；每端点一个文件。
    覆盖加入监控、列表 / 详情、调间隔、手动轮询、概览。

设计说明：
    - 本域只做入参校验与序列化，不算涨跌口径、不轮询、不发请求
    - 后台定时轮询由 ``api.boot.warmup`` 挂 ``domains.watch.scheduler``
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.watch import (
    add_targets,
    delete_target,
    get_target,
    list_targets,
    patch_target,
    poll,
    summary,
)

router = APIRouter(prefix="/v1/watch", tags=["watch"])
router.include_router(add_targets.router)
router.include_router(list_targets.router)
router.include_router(get_target.router)
router.include_router(patch_target.router)
router.include_router(delete_target.router)
router.include_router(summary.router)
router.include_router(poll.router)
