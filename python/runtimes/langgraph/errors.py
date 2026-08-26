"""Graph run 错误分类 — billing / network / rate_limit / other。"""

from __future__ import annotations

from enum import StrEnum


class ErrorKind(StrEnum):
    BILLING = "billing"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    OTHER = "other"


class GraphNodeError(Exception):
    """节点执行失败，携带可恢复语义。"""

    def __init__(self, message: str, *, kind: ErrorKind = ErrorKind.OTHER) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def classify_exception(error: BaseException) -> ErrorKind:
    text = str(error).lower()
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status in (402,):
        return ErrorKind.BILLING
    if status == 429:
        return ErrorKind.RATE_LIMIT
    billing_hints = (
        "insufficient_quota",
        "insufficient balance",
        "billing",
        "payment",
        "quota exceeded",
        "余额不足",
        "欠费",
        "credit",
        "402",
    )
    if any(h in text for h in billing_hints):
        return ErrorKind.BILLING
    network_hints = (
        "timeout",
        "timed out",
        "connection",
        "network",
        "dns",
        "unreachable",
        "reset by peer",
        "temporarily unavailable",
        "断网",
        "name or service not known",
    )
    if any(h in text for h in network_hints):
        return ErrorKind.NETWORK
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return ErrorKind.RATE_LIMIT
    return ErrorKind.OTHER
