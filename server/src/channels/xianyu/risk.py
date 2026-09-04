"""闲鱼风控判定。

职责：
    根据响应文案 / URL 判断是否触发风控（滑块、punish 页等），
    供扫码 Channel 与 renew 流程分支。

设计说明：
    - 平台：闲鱼（xianyu）；关键字与 URL token 对齐淘系常见风控页
    - 只做判定，不负责解滑块（滑块在 browser.slider / renew）
"""

from __future__ import annotations

RISK_KEYWORDS = (
    "FAIL_SYS_USER_VALIDATE",
    "RGV587",
    "USER_VALIDATE",
    "punish",
    "captcha",
    "被挤爆",
    "FAIL_SYS_ILLEGAL_ACCESS",
)

PUNISH_URL_TOKENS = ("punish", "captcha", "_____tmd_____")


def is_risk_control_text(text: str) -> bool:
    return any(keyword in text for keyword in RISK_KEYWORDS)


def page_is_punish(url: str) -> bool:
    lowered = (url or "").lower()
    return any(token in lowered for token in PUNISH_URL_TOKENS)


class RiskControlError(Exception):
    """闲鱼风控拦截 — 需浏览器过滑块。"""
