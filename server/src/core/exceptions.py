"""FastAPI 全局异常处理。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.logging import error
from src.shared.errors import AppError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        # 404 多为「尚不存在」探路（如新建 work 先 GET），不当 ERROR 刷屏
        if exc.status_code >= 500:
            error(exc.message, {"code": exc.code, "status": exc.status_code})
        elif exc.status_code >= 400:
            logging.getLogger("dingda").warning(
                "%s code=%s status=%s",
                exc.message,
                exc.code,
                exc.status_code,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "code": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error("请求参数校验失败", {"path": request.url.path, "errors": exc.errors()})
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "code": "validation_error",
                "message": "请求参数不合法",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logging.getLogger("dingda").exception(
            "未处理异常",
            extra={"_ctx": {"path": request.url.path, "error": str(exc)}},
        )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "code": "internal_error",
                "message": "服务器内部错误",
            },
        )
