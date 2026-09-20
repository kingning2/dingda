"""主编排：接用户一句话，派活给子 agent，收结果，判断够不够。

职责：
    跑一次工具循环，工具就是三个子 agent（爬虫 / 修复 / 验证）外加两个兜底动作
    （扫码登录、开有头窗口过风控）、一个选品动作（``select_products``），
    最后用 ``finish`` 收尾。

设计说明：
    - **决策只在主编排**：换不换词、修不修、验不验、够不够，都由它判断。子 agent
      只执行不决策 —— 让爬虫自己决定去修选择器，全局就没人知道发生过什么。
      ``select_products`` 是个**工具不是子 agent**：提候选词本来就是主编排的活，
      算分是 ``crawler.selection`` 的纯函数。把排名塞进一个 LLM 循环里，反而让
      「分是怎么来的」变得不可见。
    - 子 agent 是**一次工具调用**：主编排的循环里调 ``crawl`` 就是跑完整个爬虫子
      agent。不嵌套图，才不会把「谁在等谁」变成一团。
    - 异常分流全靠子 agent 回报里的 ``issues[].error_code``：
      ``crawler.needs_repair`` → 走修复 + 验证；``channel.risk`` → 开有头窗口；
      ``account.session_expired`` → 发扫码。
    - 正文推前端（``stream=True``）：只有主编排的话是给用户看的。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Final

from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec, build_tools, run_react
from agent.subagents import crawler as crawler_agent
from agent.subagents import repair as repair_agent
from agent.subagents import validator as validator_agent
from agent.tools import appraise as appraise_tool
from agent.tools import login as login_tool
from agent.tools import risk as risk_tool
from agent.tools import select as select_tool

logger = logging.getLogger("dingda.agent.orchestrator")

SYSTEM_PROMPT = """你是叮答的主编排，负责把用户的一句话变成一次完整的取数或选品任务。

你能派的人：
- crawl：爬虫，按你说的平台与关键词去搜、去看详情。它只给真实数据。
- select_products：选品，用户**不知道该卖什么**时用它。你给它几个候选品类关键词，
  它逐个去搜、各抓几条详情，再用确定性打分器按需求热度 / 竞争密度 / 入手门槛 /
  售出验证排名，回报一张带理由的候选表。打分是算出来的，不是它想出来的。
- appraise_item：鉴定，用户**已经看中了一个具体商品**（给了链接或 id）问「值不值得买 /
  买来转卖划不划算」时用它。它把这个商品和一批同款摆一起，按价差空间 / 需求热度 /
  竞争密度 / 售出验证给判词。判词只有 值得买 / 谨慎 / 不值得 / 判不了 四种，照抄。
- repair_selectors：修复，页面结构变了抽不到东西时，让它提一组新的候选选择器。
  传 section=dom 修搜索/列表页（要带 query），section=detail_dom 修详情页。
- validate_selectors：验证，拿候选选择器真抽一次，通过才热更新配置。
- login：某平台登录失效时，让用户扫码。
- open_headed_browser：自动过不了风控时，开个窗口让用户手动过。

工作流：
1. 先判断用户要的是哪种：
   - 用户给了**一个具体商品的链接或 id**，问「值不值得买 / 能不能转卖 / 划不划算」
     → 调 appraise_item，把链接或 id 原样传进去。**不要**自己编一个 item_id。
   - 用户问「我该卖什么 / 帮我决定 / 什么好卖」而**没给出具体品类** → 调 select_products，
     自己提 2~3 个具体候选品类。**不要**自己编个关键词去 crawl，再把商品列表当结论。
   - 用户给了明确的平台 + 关键词 → 用 crawl 派活。
2. 看回报：
   - issues 里有 crawler.needs_repair（抽取失效）→ 看 issue 的 section 字段：
     section=dom 修搜索页（带 query），section=detail_dom 修详情页（带 item_id）。
     调 repair_selectors 拿候选，再调 validate_selectors 验证并热更新，
     然后重新 crawl 继续原任务。
   - issues 里有 channel.risk（风控）→ 先让爬虫换个词 / 换个时间再试一次；
     还是不行就调 open_headed_browser，让用户手动过。
   - issues 里有 account.session_expired / account.cookie_required → 调 login，
     先一句话告诉用户要扫码，等扫码结果再继续。
3. 自己判断够不够：不够就继续派活（换词、补详情），够了就调 finish。

规矩：
- 不要用自己脑子里的商品信息回答用户，一切以工具回报为准。
- **选品结论只能来自 select_products 的 candidates**：汇报里出现的每一个品类都必须能在
  candidates 里找到对应的一行，分和理由都照抄它给的。excluded 里的候选、以及这一轮
  没抓过的平台（比如额度失效的 1688、根本没接的拼多多），一律不许写进结论。
- **选品必须量足才许 finish**：select_products 回来后，若任一候选的 evidence_gaps
  里还有需求热度或售出验证「未量到」，或第一与第二名的分差不足 10 分，就必须再派
  一轮 —— 换一批更具体的词，或换一个平台交叉量。两轮后如仍有缺口，如实说哪项
  没量到。只跑一轮就把「未量到」糊过去当结论，比不给建议更糟。
- **货源没量到就直说「没量到」**：用户问「货从哪来」时，若这一轮没实际抓到货源
  （没调过 crawl，或 1688 报了 channel.ali1688_auth / channel.ali1688_gateway 这类错），
  就如实回答「这次没量到货源」。**不要**替没抓过的平台描述它的供应商、起订量、价格带 ——
  那是编的，比不给建议更糟。实测过：刚推荐完品类就又凭空夸 1688「低起订量供应商
  较多」，而那一轮压根没碰过 1688。
- 候选表里 evidence_gaps 写着「没量到」的维度，汇报时要如实说「这项没量到」，
  不要拿一个数糊过去，也不要说成「不看好」。
- **鉴定的判词与分数不许改口径**：appraise_item 回报的 verdict 只有 worth / caution /
  skip / insufficient 四种，照抄它的中文 verdict_label，不要自己升级或降级。
  comparables 里 is_target 为 true 的那一行是**本商品自己**，正文里说的价格必须对得上它。
  价差只是毛价差，不含手续费与运费 —— 不要说成「能赚多少」。
- 派活只派一步，不要一次下好几个互相依赖的指令。
- 每做一个动作前，先用一句简短的话告诉用户你在做什么。
- 满足用户要求后就 finish，不要无限加搜。
"""

# 决策语气的词表：命中就在提示词最前面插一条硬指令。
_DECISION_HINTS: Final = (
    "卖什么",
    "卖啥",
    "卖点什么",
    "不知道卖",
    "不知道做什么",
    "帮我决定",
    "帮我选",
    "选品",
    "什么好卖",
    "做什么生意",
    "推荐个品类",
    "推荐品类",
)

_DECISION_NUDGE = (
    "【本轮是选品请求，不是取数请求】用户没有说明要卖什么，你别问、也别自己编个关键词"
    "去 crawl 然后把商品列表当结论。必须先调 select_products，自己提 2~3 个具体品类"
    "关键词去量。最后汇报里出现的每一个品类，都必须能在它的 candidates 里找到对应的行。"
    "用户若问「货从哪来」而你这一轮没真抓到货源，就直说「这次没量到货源」，"
    "不要替 1688 / 拼多多这些没碰过的平台描述供应商与起订量。"
)

# 鉴定语气的词表：命中就**不**算选品请求。用户的措辞常常两种意图混着来
# （「帮我选一下这个值不值得买」既像选品又是鉴定），只看「帮我选」会把他推去
# 提候选品类 —— 而他问的是手里这一件。
_APPRAISAL_HINTS: Final = (
    "值得买",
    "值不值得",
    "值不值",
    "能不能买",
    "该不该买",
    "划不划算",
    "买来转卖",
)

# 商品链接 / 商品 id：钉着具体商品说话时问的是这一件。形状只认闲鱼那两种
# （与 ``tools.appraise.item_id_from_url`` 同一形状），不是就不猜。
_ITEM_MARKER = re.compile(r"[?&]id=\d{5,}|/item/\d{5,}")


async def run_orchestrator(
    ctx: RunContext,
    prompt: str,
    *,
    platform_hint: str | None = None,
    context_messages: list[dict[str, Any]] | None = None,
    max_steps: int = 12,
) -> dict[str, Any]:
    """跑一次主编排；返回 ``{ok, summary, steps, exit_code}``。"""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in context_messages or ():
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}:
            messages.append({"role": str(item["role"]), "content": str(item.get("content") or "")})
    if _is_decision_request(prompt):
        # 实测过：光靠 SYSTEM_PROMPT 里的规矩拦不住 —— 模型会自己编个关键词去 crawl，
        # 再把商品列表包装成结论。所以在用户这轮话前面钉一条硬指令。
        logger.info("识别为选品请求 run=%s", ctx.run_id)
        prompt = f"{_DECISION_NUDGE}\n\n{prompt}"
    if platform_hint:
        prompt = f"{prompt}\n（本轮优先平台：{platform_hint}）"
    messages.append({"role": "user", "content": prompt})

    result = await run_react(
        llm=ctx.llm.chat_model,
        tools=build_tools(ctx, _specs()),
        messages=messages,
        ctx=ctx,
        max_steps=max_steps,
        stop_tools=("finish",),
        stream=True,
    )

    summary = str(result.stop_args.get("summary") or "").strip() or result.text.strip()
    logger.info(
        "主编排收工 run=%s steps=%s stop=%s exit=%s",
        ctx.run_id,
        result.steps,
        result.stop_name,
        result.exit_code,
    )
    return {
        "ok": result.exit_code == 0,
        "summary": summary,
        "steps": result.steps,
        "stop_name": result.stop_name,
        "exit_code": result.exit_code,
    }


def _is_decision_request(prompt: str) -> bool:
    """用户这轮是不是在问「卖什么」。

    只看提示词命中，不看平台 / 关键词 —— 分不清「用户没给品类」和「用户给了品类」
    时，宁可多钉一条指令：钉错了只是多说一句，漏钉了就是一个编出来的结论。

    两条例外都指向同一件事：用户在说**一个具体的商品**，那就不是选品意图。
    给了链接 / 商品 id（钉着这一件），或者用了鉴定语气（值不值得 / 能不能买
    / 划不划算），一律不算 —— 「帮我选一下这个值不值得买」里的「帮我选」只是
    措辞，把他推去提候选品类是答错了题。
    """
    text = prompt or ""
    if _ITEM_MARKER.search(text) or any(hint in text for hint in _APPRAISAL_HINTS):
        return False
    return any(hint in text for hint in _DECISION_HINTS)


class CrawlTaskInput(BaseModel):
    """派活给爬虫。"""

    task: str = Field(
        description=(
            "给爬虫的一句话任务，必须讲清：平台（xianyu / xiaohongshu / ali1688）、"
            "搜索关键词、要看几条、要不要拉详情"
        )
    )


class RepairTaskInput(BaseModel):
    """派活给修复。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    item_id: str = Field(description="抽取失效的商品 / 笔记 id")
    section: str = Field(default="detail_dom", description="修复目标：dom（搜索/列表）或 detail_dom（详情）")
    query: str = Field(default="", description="搜索页修复时的关键词；section=dom 时必传")
    xsec_token: str | None = Field(default=None, description="小红书详情偶发需要")


class ValidateTaskInput(BaseModel):
    """派活给验证。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    item_id: str = Field(description="商品 / 笔记 id")
    selectors: dict[str, Any] = Field(description="repair_selectors 给的候选选择器")
    section: str = Field(default="detail_dom", description="修复目标：dom（搜索/列表）或 detail_dom（详情）")
    query: str = Field(default="", description="搜索页修复时的关键词；section=dom 时必传")
    xsec_token: str | None = Field(default=None, description="小红书详情偶发需要")


class FinishInput(BaseModel):
    """收尾：把结果交给用户。"""

    summary: str = Field(description="用中文简短汇报拿到了什么、缺什么；不要复述原始 JSON")


async def _crawl(ctx: RunContext, task: str) -> dict[str, Any]:
    """派一次活给爬虫子 agent。"""
    return await crawler_agent.run_crawler(ctx, task)


async def _repair(
    ctx: RunContext,
    platform: str,
    item_id: str,
    section: str = "detail_dom",
    query: str = "",
    xsec_token: str | None = None,
) -> dict[str, Any]:
    """派一次活给修复子 agent。"""
    return await repair_agent.run_repair(
        ctx, platform=platform, item_id=item_id, section=section, query=query, xsec_token=xsec_token
    )


async def _validate(
    ctx: RunContext,
    platform: str,
    item_id: str,
    selectors: dict[str, Any],
    section: str = "detail_dom",
    query: str = "",
    xsec_token: str | None = None,
) -> dict[str, Any]:
    """派一次活给验证子 agent。"""
    return await validator_agent.run_validate(
        ctx,
        platform=platform,
        item_id=item_id,
        selectors=selectors,
        section=section,
        query=query,
        xsec_token=xsec_token,
    )


async def _finish(ctx: RunContext, summary: str) -> dict[str, Any]:
    """收尾：把总结交给前端。"""
    return {"ok": True, "summary": summary}


def _specs() -> tuple[ToolSpec, ...]:
    """主编排能调的全部工具：三个子 agent + 选品 + 鉴定 + 两个兜底 + 收尾。"""
    return (
        ToolSpec(
            name="crawl",
            label="派活 · 爬虫",
            description=(
                "让爬虫去取真实数据。任务里讲清平台、关键词、要看几条、要不要拉详情。"
                "回报里有 items（拿到什么）与 issues（撞到什么）。"
                "**已知要卖什么**时用它；不知道该卖什么用 select_products。"
            ),
            args=CrawlTaskInput,
            fn=_crawl,
        ),
        ToolSpec(
            name="repair_selectors",
            label="派活 · 修复",
            description=(
                "抽取失效（issues 里有 crawler.needs_repair）时调它，拿一组候选选择器。"
                "拿到后必须再调 validate_selectors，不要直接采用。"
            ),
            args=RepairTaskInput,
            fn=_repair,
        ),
        ToolSpec(
            name="validate_selectors",
            label="派活 · 验证",
            description=(
                "拿 repair_selectors 给的候选选择器验证一次；通过会自动热更新配置，"
                "之后重新 crawl 就能用新配置抓到。"
            ),
            args=ValidateTaskInput,
            fn=_validate,
        ),
        ToolSpec(
            name="finish",
            label="汇报结果",
            description="任务完成（或确认做不下去）时调用，把结果交给用户。",
            args=FinishInput,
            fn=_finish,
        ),
        *login_tool.TOOLS,
        *risk_tool.TOOLS,
        *select_tool.TOOLS,
        *appraise_tool.TOOLS,
    )
