"""应用级业务异常定义。

职责：
    提供可在 domain / api 层抛出的统一异常类型，
    便于在 FastAPI 异常处理器中映射为稳定的 HTTP 状态码与错误 JSON。

字段说明：
    code         机器可读错误码，如 ``agent.run_failed``
    message      人类可读说明
    status_code  建议的 HTTP 状态码，默认 400

使用示例::

    raise AppError("crawler.not_found", "任务不存在", status_code=404)

由 ``src.core.exceptions.register_exception_handlers`` 统一映射为 JSON 响应并写日志。
"""

from __future__ import annotations


class AppError(Exception):
    """带错误码与 HTTP 状态的业务异常基类。"""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def session_expired_error(platform: str) -> AppError:
    label = {"xianyu": "闲鱼", "xiaohongshu": "小红书"}.get(platform, "账号")
    return AppError(
        "account.session_expired",
        f"{label}登录已过期，请重新扫码登录",
        status_code=401,
    )


def risk_control_error(message: str) -> AppError:
    return AppError("channel.risk", message, status_code=403)


def sign_error(message: str) -> AppError:
    return AppError("channel.sign_failed", message, status_code=400)


def not_found_error(message: str) -> AppError:
    return AppError("crawler.not_found", message, status_code=404)


def rate_limited_error(message: str) -> AppError:
    return AppError("channel.rate_limited", message, status_code=429)
