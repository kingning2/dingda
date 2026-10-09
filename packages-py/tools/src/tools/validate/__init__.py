"""DOM 选择器校验 Tool（只给修复子 agent 用）。

职责：
    把候选选择器 POST 回**修复现场**那个宿主进程（临时监听），在同一页面上跑平台
    抽取脚本，把真实 payload 或失败原样拿回来，让子 agent 自己判断要不要改。

设计说明：
    - 地址来自 ``DINGDA_VALIDATE_URL``（父侧 repair 流程注入）；没有就报错 —— 这个
      工具只在修复子 agent 的会话里有意义
    - 不做「对/错」判定：判定标准在平台 adapter 的 ``payload_ok`` 里，由父侧编排
      与子 agent 的 prompt 共同约定

使用示例：
    out = await run_validate(ValidateInput(selectors={"price": "[class*=\"price\"]"}))
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("dingda.tools.validate")

TOOL_NAME = "validate_selectors"
TOOL_DESCRIPTION = (
    "修 DOM 选择器时用：把候选选择器放到「正在修的那个页面」上试跑，"
    "返回平台抽取脚本的真实输出（或失败原因）。出完选择器先调它验证，"
    "不对就按返回内容调整再调一次。"
)
DEFAULT_TIMEOUT_S = 90.0


class ValidateInput(BaseModel):
    """校验入参。"""

    selectors: dict[str, str] = Field(description="字段名 → CSS 选择器。")


class ValidateOutput(BaseModel):
    """校验结果。"""

    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="平台抽取脚本输出：成功是字段值，失败带 error。",
    )
    error: str | None = Field(default=None, description="校验通道本身失败时的错误码。")


async def run_validate(inp: ValidateInput) -> ValidateOutput:
    """把选择器发去修复现场跑一遍。"""
    url = (os.getenv("DINGDA_VALIDATE_URL") or "").strip()
    if not url:
        return ValidateOutput(error="validate-url-missing")
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_S) as client:
            resp = await client.post(url, json={"selectors": inp.selectors})
    except Exception as exc:  # noqa: BLE001
        logger.warning("validate post failed: %s", exc)
        return ValidateOutput(error="validate-unreachable")
    if resp.status_code != 200:
        return ValidateOutput(error=f"validate-http-{resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        return ValidateOutput(error="validate-bad-json")
    if not isinstance(body, dict):
        return ValidateOutput(error="validate-bad-payload")
    logger.info(
        "validate done keys=%s error=%s",
        sorted(inp.selectors)[:8],
        body.get("error"),
    )
    return ValidateOutput(payload=body)
