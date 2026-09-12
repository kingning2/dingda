"""1688 网关请求签名。

职责：
    用 AK 生成 x-csk-* 签名头，供 client 调用官方网关。

设计说明：
    - 算法对齐 1688-product-find Skill 的 HMAC-SHA256 签名
    - x-csk-version 使用叮答客户端版本常量

使用示例：
    headers = build_auth_headers("POST", path, body_str)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import uuid
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from channels.ali1688.ak import get_ak

logger = logging.getLogger("dingda.channel.ali1688.sign")

# 签名头里的客户端版本（非 Skill 版本号）
CLIENT_VERSION = "1.0.0"
CONTENT_TYPE = "application/json"


def _content_md5(body: str) -> str:
    """Body MD5 再 Base64。"""
    if not body:
        return ""
    digest = hashlib.md5(body.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


def _canonicalized_resource(uri: str) -> str:
    """规范化 path + 排序 query。"""
    parsed = urlparse(uri)
    path = parsed.path or "/"
    if not parsed.query:
        return path
    params = parse_qs(parsed.query, keep_blank_values=True)
    parts: list[str] = []
    for key, values in sorted(params.items()):
        for value in sorted(values):
            parts.append(f"{quote(key, safe='')}={quote(value, safe='')}")
    return f"{path}?{'&'.join(parts)}"


def build_signature(
    method: str,
    uri: str,
    body: str,
    *,
    ak_id: str,
    ak_secret: str,
    content_type: str = CONTENT_TYPE,
) -> dict[str, str]:
    """构建带 HMAC 签名的请求头。"""
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex[:8]
    content_md5 = _content_md5(body)

    csk_headers = {
        "x-csk-ak": ak_id,
        "x-csk-time": timestamp,
        "x-csk-nonce": nonce,
        "x-csk-content-md5": content_md5,
        "x-csk-version": CLIENT_VERSION,
    }

    canonicalized_headers = "".join(
        f"{key.lower()}:{csk_headers[key].strip()}\n" for key in sorted(csk_headers)
    )
    string_to_sign = (
        f"{method.upper()}\n"
        f"{content_md5}\n"
        f"{content_type}\n"
        f"{timestamp}\n"
        f"{canonicalized_headers}"
        f"{_canonicalized_resource(uri)}"
    )
    signature = hmac.new(
        ak_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return {
        "Content-Type": content_type,
        "x-csk-sign": base64.b64encode(signature).decode("utf-8"),
        **csk_headers,
    }


def build_auth_headers(method: str, uri: str, body: str = "") -> dict[str, str] | None:
    """读取 AK 并生成签名头；未配置则返回 None。"""
    ak_id, ak_secret = get_ak()
    if not ak_id or not ak_secret:
        logger.warning("AK 未配置")
        return None
    return build_signature(
        method=method,
        uri=uri,
        body=body,
        ak_id=ak_id,
        ak_secret=ak_secret,
    )


def sign_string_for_test(
    method: str,
    uri: str,
    body: str,
    *,
    ak_id: str,
    ak_secret: str,
    timestamp: str,
    nonce: str,
) -> str:
    """仅测试用：固定 timestamp/nonce 时的待签名串（不对外业务调用）。"""
    content_md5 = _content_md5(body)
    csk_headers: dict[str, Any] = {
        "x-csk-ak": ak_id,
        "x-csk-time": timestamp,
        "x-csk-nonce": nonce,
        "x-csk-content-md5": content_md5,
        "x-csk-version": CLIENT_VERSION,
    }
    canonicalized_headers = "".join(
        f"{key.lower()}:{str(csk_headers[key]).strip()}\n" for key in sorted(csk_headers)
    )
    return (
        f"{method.upper()}\n"
        f"{content_md5}\n"
        f"{CONTENT_TYPE}\n"
        f"{timestamp}\n"
        f"{canonicalized_headers}"
        f"{_canonicalized_resource(uri)}"
    )
