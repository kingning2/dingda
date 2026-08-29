"""闲鱼 H5 mtop HTTP 客户端（对齐 Rust ``platform::xianyu::core::mtop``）。

封装签名请求与响应解析，供商品、资料与 WebSocket token 等调用方使用。"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from dingda_sidecar.crawlers.goofish.ws.constants import APP_KEY, USER_AGENT, WEB_ORIGIN
from dingda_sidecar.crawlers.goofish.ws.cookies import (
    credential_to_cookie_header,
    now_ms,
    parse_cookies,
    sign_token,
)
from dingda_sidecar.crawlers.goofish.ws.sign import generate_sign

logger = logging.getLogger("dingda.crawlers.goofish.mtop")

H5_API_BASE = "https://h5api.m.goofish.com/h5/"


@dataclass
class MtopRequest:
    api: str
    version: str
    data: dict[str, Any]
    extra_params: dict[str, str] = field(default_factory=dict)
    use_get: bool = False

    def with_param(self, key: str, value: str) -> MtopRequest:
        self.extra_params[key] = value
        return self

    def with_get(self) -> MtopRequest:
        self.use_get = True
        return self


@dataclass
class MtopResponse:
    json: dict[str, Any]
    ret: str

    def success(self) -> bool:
        return "SUCCESS" in self.ret

    def data(self) -> Any:
        return self.json.get("data")


class MtopClient:
    """同步 mtop 客户端；TOKEN_EXPIRED 时合并 set-cookie 并重试。"""

    def __init__(self, cookie_str: str) -> None:
        self._cookie = credential_to_cookie_header(cookie_str)

    @property
    def cookie(self) -> str:
        return self._cookie

    def call(self, request: MtopRequest) -> MtopResponse:
        last: MtopResponse | None = None
        for retry in range(3):
            last = self._call_once(request)
            token_expired = "TOKEN_EXPIRED" in last.ret or "TOKEN_EXOIRED" in last.ret
            if token_expired and retry < 2:
                logger.info("mtop 令牌过期 api=%s retry=%s", request.api, retry + 1)
                time.sleep(0.5)
                continue
            return last
        assert last is not None
        return last

    def _call_once(self, request: MtopRequest) -> MtopResponse:
        cookies = parse_cookies(self._cookie)
        token = sign_token(cookies) or ""
        timestamp = str(now_ms())
        data_val = json.dumps(request.data, ensure_ascii=False, separators=(",", ":"))
        sign = generate_sign(token, timestamp, data_val)

        params: dict[str, str] = {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": timestamp,
            "sign": sign,
            "v": request.version,
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": request.api,
            "sessionOption": "AutoLoginOnly",
            **request.extra_params,
        }

        url = f"{H5_API_BASE}{request.api}/{request.version}/"
        headers = {
            "Origin": WEB_ORIGIN,
            "User-Agent": USER_AGENT,
            "Cookie": self._cookie,
            "Referer": WEB_ORIGIN,
        }

        if request.use_get:
            params["data"] = data_val
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url, headers=headers, method="GET")
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urllib.parse.urlencode({"data": data_val}).encode("utf-8")
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=25) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")
                set_cookies = resp.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"mtop 请求失败 ({request.api}): {error}") from error
        except Exception as error:  # noqa: BLE001
            raise RuntimeError(f"mtop 请求失败 ({request.api}): {error}") from error

        if set_cookies:
            self._merge_set_cookies(set_cookies)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"mtop 响应解析失败: {error}") from error

        if not isinstance(payload, dict):
            raise RuntimeError("mtop 响应不是 JSON 对象")

        ret_list = payload.get("ret")
        ret = str(ret_list[0]) if isinstance(ret_list, list) and ret_list else str(payload)
        return MtopResponse(json=payload, ret=ret)

    def _merge_set_cookies(self, set_cookies: list[str]) -> None:
        merged = parse_cookies(self._cookie)
        for cookie in set_cookies:
            first = cookie.split(";", 1)[0]
            if "=" not in first:
                continue
            name, value = first.split("=", 1)
            name = name.strip()
            if name:
                merged[name] = value.strip()
        self._cookie = "; ".join(f"{k}={v}" for k, v in merged.items())
