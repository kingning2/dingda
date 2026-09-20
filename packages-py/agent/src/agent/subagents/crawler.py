"""爬虫子 agent：按主编排派的活去取真实数据，撞墙立刻回报。

职责：
    收一个具体任务（搜什么、看哪几条），跑工具循环取数，把拿到的商品与撞到的墙
    一起报回主编排。

设计说明：
    - **只干抓取，不做决策**：要不要换词再搜、要不要去修选择器，都是主编排的事。
      子 agent 越界做决策，主编排就失去了全局判断。
    - **撞墙不自救**：风控与登录失效原样进 ``issues``，主编排据此决定是开有头窗口
      还是发扫码。工具层已经自动过了一次风控，这里不再试第二次。
    - 正文不推前端（``stream=False``）：它的结论是作为工具结果回到主编排的，
      直接推下去会同主编排自己的播报混在一起。
"""

from __future__ import annotations

import logging
from typing import Any

from agent.context import RunContext
from agent.loop import ReactResult, build_tools, run_react
from agent.tools import crawl

logger = logging.getLogger("dingda.agent.subagent.crawler")

SYSTEM_PROMPT = """你是叮答的爬虫执行者，只负责用工具取真实数据。

规矩：
- **不要凭记忆编造商品、价格、链接、id**，一切都来自工具返回。
- 任务说搜什么就搜什么，不要自己扩大范围；关键词按任务给的来。
- 一次搜索只给列表壳。要看清某一条，必须再用 fetch_detail 拉全。
- 拿够了就收手，不要为了凑数反复搜同一批词。
- 工具报 account.session_expired / account.cookie_required / channel.risk 时，
  **不要自己想办法**，把你已经拿到的东西和遇到的问题如实说清楚，交给主编排处理。
"""


async def run_crawler(ctx: RunContext, task: str, *, max_steps: int = 10) -> dict[str, Any]:
    """跑一次爬虫任务；返回 ``{ok, items, issues, summary}``。"""
    result = await run_react(
        llm=ctx.llm.chat_model,
        tools=build_tools(ctx, crawl.TOOLS),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ],
        ctx=ctx,
        max_steps=max_steps,
        stream=False,
    )
    return _collect(result)


def _collect(result: ReactResult) -> dict[str, Any]:
    """把各步工具出参收成一份回报：商品去重，问题按类汇总。"""
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    issues: list[dict[str, Any]] = []

    for step in result.tool_results:
        output = step.get("output") or {}
        for item in output.get("items") or ():
            if not isinstance(item, dict):
                continue
            key = (str(item.get("platform") or ""), str(item.get("item_id") or ""))
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        if output.get("ok") is False:
            issues.append(
                {
                    "tool": step.get("name"),
                    "platform": output.get("platform"),
                    "error_code": output.get("error_code"),
                    "message": output.get("message"),
                    "args": step.get("args") or {},
                }
            )

    logger.info("爬虫子 agent 收工 items=%s issues=%s", len(items), len(issues))
    return {
        "ok": bool(items),
        "items": items,
        "issues": issues,
        "summary": result.text.strip(),
    }
