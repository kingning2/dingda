"""Research 域路由骨架。

职责：
    占住 ``/v1/research`` 前缀；端点按一端点一文件在后续迭代补充。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/v1/research", tags=["research"])
