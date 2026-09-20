"""验证子 agent：候选选择器好不好使，好使才热更新。

职责：
    拿一组候选选择器真抽一次；抽到有效字段就写回配置（热更新），
    把「验没验过、热没热更新、撞到什么」报回主编排。

设计说明：
    - **先试后写是硬顺序**：``try_selectors`` 不通过就不许 ``commit_selectors``。
      这条既写在提示词里，也写在工具描述里 —— 模型跳过验证直接写盘会把平台抓崩。
    - 验证不通过**不重试改写**：改选择器是修复 agent 的活。验证 agent 越界改，
      就没人做「独立复核」了。
    - 回报里的 ``valid`` 与 ``hot_reloaded`` 分开：验过但没写成，主编排要能分辨
      （例如热更新写盘失败，得如实告诉用户）。
"""

from __future__ import annotations

import logging
from typing import Any

from agent.context import RunContext
from agent.loop import ReactResult, build_tools, run_react
from agent.tools import validate

logger = logging.getLogger("dingda.agent.subagent.validator")

SYSTEM_PROMPT = """你是叮答的选择器验证者：别人给了一组候选选择器，你负责判定能不能用。

规矩：
- 先调 try_selectors 真抽一次，看有没有抽到有效字段。
- **只有验证通过才调 commit_selectors** 写回配置；没通过就如实回报，不要写。
- 不要自己改选择器 —— 改是修复环节的事，你只判定。
- 撞到风控（channel.risk）或登录失效（account.session_expired）也如实回报，
  那是环境问题，不是选择器的问题。
"""


async def run_validate(
    ctx: RunContext,
    *,
    platform: str,
    item_id: str,
    selectors: dict[str, Any],
    section: str = "detail_dom",
    query: str = "",
    xsec_token: str | None = None,
    max_steps: int = 5,
) -> dict[str, Any]:
    """验证一组候选选择器；通过就热更新。返回 ``{ok, valid, hot_reloaded, ...}``。"""
    task = (
        f"platform={platform} section={section} item_id={item_id}\n"
        f"待验证的选择器：{selectors}"
    )
    if query:
        task += f"\nquery={query}"
    if xsec_token:
        task += f"\nxsec_token={xsec_token}"

    result = await run_react(
        llm=ctx.llm.chat_model,
        tools=build_tools(ctx, validate.TOOLS),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请验证这组选择器，通过就热更新：\n{task}"},
        ],
        ctx=ctx,
        max_steps=max_steps,
        stream=False,
    )
    return _collect(result, platform=platform, item_id=item_id, section=section)


def _collect(
    result: ReactResult,
    *,
    platform: str,
    item_id: str,
    section: str = "detail_dom",
) -> dict[str, Any]:
    """判定验证与热更新各成不成，以及路上撞到什么。"""
    valid = False
    hot_reloaded = False
    issues: list[dict[str, Any]] = []

    for step in result.tool_results:
        output = step.get("output") or {}
        name = step.get("name")
        if name == "try_selectors" and output.get("ok") is True:
            valid = True
        if name == "commit_selectors" and output.get("ok") is True:
            hot_reloaded = True
        if output.get("ok") is False:
            issues.append(
                {
                    "tool": name,
                    "platform": output.get("platform"),
                    "error_code": output.get("error_code"),
                    "message": output.get("message"),
                }
            )

    logger.info(
        "验证子 agent 收工 valid=%s hot_reloaded=%s issues=%s",
        valid,
        hot_reloaded,
        len(issues),
    )
    return {
        "ok": valid and hot_reloaded,
        "platform": platform,
        "item_id": item_id,
        "section": section,
        "valid": valid,
        "hot_reloaded": hot_reloaded,
        "issues": issues,
        "summary": result.text.strip(),
    }
