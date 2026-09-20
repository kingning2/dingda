"""修复子 agent：看 DOM，提一组候选选择器交回去。

职责：
    对指定平台 + 商品 id 打开详情页看 DOM 结构，产出一组候选选择器（json），
    交给主编排转验证。**它自己不写盘**。

设计说明：
    - 产出走 ``submit_patch`` 工具而不是「自己写文件」：写盘是验证通过之后的事，
      让修复 agent 写等于把「改坏了」直接落到线上配置。
    - 提交即收工（``stop_tools``）：提完候选就结束循环，不接着自我审查 ——
      审不审查由验证 agent 做，两个角色分开才查得动。
    - 只改 ``detail_dom`` 这一节的选择器，``signals`` 那类是平台判断风控 / 登录墙的
      依据，动不得。
"""

from __future__ import annotations

import logging
from typing import Any

from agent.context import RunContext
from agent.loop import ReactResult, build_tools, run_react
from agent.tools import repair

logger = logging.getLogger("dingda.agent.subagent.repair")

SYSTEM_PROMPT = """你是叮答的选择器修复者：页面结构变了，抽不到字段，你要给出新的选择器。

规矩：
- 先调 inspect_dom 看真实 DOM 结构，**再**提候选；不要凭印象猜选择器。
- 只给 required_fields 里列出的字段，一个都不能少，也不要多加。
- 选择器写 CSS：优先用稳定的 class / 属性，别用第 N 个子节点这种一改版就断的定位。
- **不要用 :has-text() 这类非 CSS 伪类**，页面跑 querySelector 会直接报错。
- 看清字段落在哪个元素上：容器元素抽出来会混进一堆噪音文本。
- 提完就调 submit_patch 收工，不要自行判断是否有效 —— 那是验证环节的事。
"""


async def run_repair(
    ctx: RunContext,
    *,
    platform: str,
    item_id: str,
    section: str = "detail_dom",
    query: str = "",
    xsec_token: str | None = None,
    max_steps: int = 6,
) -> dict[str, Any]:
    """修一组选择器；返回 ``{ok, platform, item_id, selectors, issues, summary}``。"""
    task = f"platform={platform} section={section} item_id={item_id}"
    if query:
        task += f" query={query}"
    if xsec_token:
        task += f" xsec_token={xsec_token}"

    result = await run_react(
        llm=ctx.llm.chat_model,
        tools=build_tools(ctx, repair.TOOLS),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请修复这条商品的抽取选择器并交出候选：{task}"},
        ],
        ctx=ctx,
        max_steps=max_steps,
        stop_tools=("submit_patch",),
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
    """取候选选择器与路上撞到的问题。"""
    selectors: dict[str, Any] = {}
    if result.stop_name == "submit_patch":
        raw = result.stop_args.get("selectors")
        if isinstance(raw, dict):
            selectors = raw

    issues: list[dict[str, Any]] = []
    for step in result.tool_results:
        output = step.get("output") or {}
        if output.get("ok") is False:
            issues.append(
                {
                    "tool": step.get("name"),
                    "platform": output.get("platform"),
                    "error_code": output.get("error_code"),
                    "message": output.get("message"),
                }
            )

    logger.info("修复子 agent 收工 selectors=%s issues=%s", len(selectors), len(issues))
    return {
        "ok": bool(selectors),
        "platform": platform,
        "item_id": item_id,
        "section": section,
        "selectors": selectors,
        "issues": issues,
        "summary": result.text.strip(),
    }
