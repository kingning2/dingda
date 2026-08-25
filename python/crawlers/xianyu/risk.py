"""闲鱼风控文案判定 — token / mtop 验证码拦截关键字。"""

from __future__ import annotations

import json
from typing import Any

_RISK_KEYWORDS = (
    "FAIL_SYS_USER_VALIDATE",
    "RGV587",
    "USER_VALIDATE",
    "punish",
    "captcha",
    "被挤爆",
    "FAIL_SYS_ILLEGAL_ACCESS",
)


def is_risk_control_text(text: str) -> bool:
    """判断文本是否为闲鱼风控拦截（验证码 / 签名异常 / 频率限制）。"""
    return any(keyword in text for keyword in _RISK_KEYWORDS)


def extract_punish_url(text: str) -> str | None:
    """从风控错误原文中提取惩罚页 URL（若有）。"""
    json_start = text.find("{")
    if json_start >= 0:
        try:
            value: Any = json.loads(text[json_start:])
            url = (value.get("data") or {}).get("url")
            if isinstance(url, str):
                normalized = url.replace("\\/", "/")
                if "punish" in normalized or "captcha" in normalized:
                    return normalized
        except json.JSONDecodeError:
            pass

    start = text.find("https://")
    if start < 0:
        return None
    rest = text[start:]
    end = len(rest)
    for ch in ('"', " ", "}", "'"):
        idx = rest.find(ch)
        if idx >= 0:
            end = min(end, idx)
    url = rest[:end].replace("\\/", "/")
    if "punish" in url or "captcha" in url:
        return url
    return None


class RiskControlError(Exception):
    """闲鱼风控拦截 — 需浏览器过滑块。"""

    def __init__(self, detail: str, *, punish_url: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.punish_url = punish_url
