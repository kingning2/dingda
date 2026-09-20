"""鉴定工具：把「这个商品值不值得买」变成一次可复算的取数 + 打分。

职责：
    主编排拿到一个具体商品的 id 或链接时调 ``appraise_item`` —— 它先拉本商品的
    详情，再从标题提出同款检索词去搜一批同款，按轮次给其中几条补详情，最后调
    ``crawler.appraisal`` 的确定性打分器下判词，回报结论与一张同款表。

设计说明：
    - **一个工具，不是子 agent**：和 ``tools/select.py`` 同理 —— 子 agent 唯一不可
      替代的活是「拿主意」，而「提同款词」这件事主编排本来就能做（也可以显式传
      ``query`` 进来）。把确定性判词藏进一个 LLM 循环里，只会让「判词是怎么来的」
      变得不可见。
    - **复用 ``agent.tools.crawl`` 的两个动作**，不自己开浏览器、不自己重试：
      ``search_items`` / ``fetch_detail`` 已经带了风控重试与 ``ok=False`` 语义。
    - **上限卡在代码里，不写在提示词里**：``details`` 用 pydantic 的 ``le`` 封顶，
      再加 ``_DEADLINE_S`` 墙钟预算兜住跑飞。逐条闲鱼详情实测 14~30s，还要过
      ``DINGDA_DETAIL_MIN_INTERVAL_S`` 的节流闸门，靠模型自觉是拦不住的。
    - **失败不炸穿**：单个同款拉不到详情只记一条 ``issues``，那一行退化成「只有价格」
      的壳继续参与价格基线；只有**本商品自己**拉不到详情才 ``ok=False`` —— 那是
      鉴定的主语，缺了它什么都算不出来。
    - **同款集必须剔掉本商品自己**：``_shells`` 按 item_id 剔一次，``appraise_item``
      内部再幂等地剔一次。不剔的话中位价被自己拉平、价差恒 0，判词会永远「不值得」。
    - **出参不带顶层 ``platform``**：前端 ``extractProducts`` 看到这个键就认领，
      会把鉴定载荷当商品列表塞进商品面板。平台在 ``target.platform`` 里，
      同款数组叫 ``comparables``。
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Final

from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec
from agent.tools.crawl import fetch_detail, search_items
from crawler.appraisal import appraise_item

logger = logging.getLogger("dingda.agent.tool.appraise")

SUPPORTED_PLATFORMS: Final = ("xianyu", "xiaohongshu")

# 同款搜索要多少条：条数即「竞争密度」的底样，价格基线也靠它铺。
_SEARCH_LIMIT = 30

# 整次鉴定的墙钟预算。本商品一条详情 + 同款最多 4 条，实测一条 14~30s，撞风控过
# 滑块能到 90s。这个数看着大，职责是**兜住跑飞**，正常路径靠 pydantic 的条数上限收口。
# 超预算不硬打断在跑的那次抓取，只在**下一条开抓之前**停手，剩下的标 partial。
_DEADLINE_S = 240.0

# 同款检索词的启发式上限：标题太长会把搜索稀释成一堆不相干的词。
_QUERY_MAX = 20

# 标题里常见的营销词，提检索词时剔掉 —— 它们对「找同款」没有区分度。
_NOISE_WORDS: Final = (
    "全新",
    "未拆封",
    "包邮",
    "正品",
    "现货",
    "特价",
    "清仓",
    "闲置",
    "二手",
    "低价",
    "秒杀",
    "专柜",
    "官方",
    "自用",
    "低价出",
    "急出",
)

_BRACKETED = re.compile(r"[【\[（(][^】\]）)]*[】\]）)]")
_ID_IN_QUERY = re.compile(r"[?&]id=(\d{5,})")
_ID_IN_PATH = re.compile(r"/item/(\d{5,})")


class AppraiseInput(BaseModel):
    """鉴定入参。"""

    platform: str = Field(default="xianyu", description="平台：xianyu / xiaohongshu")
    item_id: str = Field(
        default="",
        description="本商品 id。**优先用它** —— 来自搜索结果，不要手编。",
    )
    url: str = Field(
        default="",
        description="商品链接；只给链接时从这里取 id（闲鱼 ?id= 与 /item/<id> 两种形状）。",
    )
    query: str = Field(
        default="",
        description=(
            "找同款的检索词。留空则由工具从本商品标题里截。"
            "截得不好时（同款不「同款」）才自己传一个更准的。"
        ),
    )
    details: int = Field(
        default=4,
        ge=0,
        le=4,
        description="给几条同款补详情来量需求。详情很慢，默认 4 条。",
    )


async def appraise_item_tool(
    ctx: RunContext,
    platform: str = "xianyu",
    item_id: str = "",
    url: str = "",
    query: str = "",
    details: int = 4,
) -> dict[str, Any]:
    """鉴定一个商品：本商品详情 → 同款搜索 → 补详情 → 确定性判词。"""
    plat = str(platform or "").strip().lower()
    if plat not in SUPPORTED_PLATFORMS:
        return _fail(plat, "agent.invalid_input", f"不支持的平台 {platform or '(空)'}")

    target_id = str(item_id or "").strip() or item_id_from_url(url)
    if not target_id:
        return _fail(
            plat,
            "agent.invalid_input",
            "要给出 item_id，或一个能认出商品 id 的链接；都没有就先派一次 crawl 拿 id",
        )

    started = time.monotonic()
    issues: list[dict[str, Any]] = []
    partial = False

    # 本商品详情 —— 鉴定的主语。拉不到就没得算，直接失败。
    detail = await fetch_detail(ctx, plat, target_id, url=str(url or "").strip() or None)
    if not detail.get("ok"):
        code = str(detail.get("error_code") or "crawler.failed")
        return _fail(plat, code, f"拿不到本商品详情：{detail.get('message') or code}")
    target = _first_item(detail)
    if target is None:
        return _fail(plat, "crawler.empty", "本商品详情是空的，没得鉴定")

    # 同款检索词：显式给的优先；没给就从标题里截，并在出参回显 —— 用户要看得见
    # 「同款是拿什么搜出来的」，否则价差对不上时无从追。
    keywords = str(query or "").strip() or query_from_title(str(target.get("title") or ""))
    if not keywords:
        return _fail(plat, "crawler.empty", "本商品没有可用的标题，提不出同款检索词")

    peers, failure = await _shells(ctx, platform=plat, keyword=keywords, exclude=target_id, issues=issues)
    if failure is not None:
        # 搜索本身挂了（风控 / 空结果）：这是真失败，交回主编排按 error_code 分流。
        return _fail(plat, failure, f"同款搜索没成功：{keywords}")

    budget = max(0, min(int(details), 4))
    for _round in range(budget):
        if ctx.cancelled():
            partial = True
            issues.append(_issue("agent.cancelled", "运行被取消"))
            break
        if _over_budget(started):
            partial = True
            issues.append(_issue("agent.deadline", f"超出 {_DEADLINE_S:.0f}s 预算，剩余同款未拉详情"))
            break
        if not await _attach_detail(ctx, platform=plat, peers=peers, issues=issues):
            break

    out = appraise_item(
        platform=plat,
        target=target,
        comparables=peers,
        query=keywords,
        partial=partial,
        issues=issues,
    )
    out["ok"] = True
    return out


def item_id_from_url(url: str) -> str:
    """从商品链接里取 id；取不到返回空串（**不猜**）。

    只认闲鱼两种形状：``?id=123456`` 与 ``/item/123456``。别的一律不猜 ——
    猜错的 id 会拉到一个不相干的商品，然后给它下一个看起来很确定的判词。
    """
    text = str(url or "")
    for pattern in (_ID_IN_QUERY, _ID_IN_PATH):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def query_from_title(title: str) -> str:
    """从标题里截一个同款检索词：去括号段、去营销词、限长。

    启发式，不追求最优 —— 截得不好时主编排可以显式传 ``query`` 纠正。
    """
    text = _BRACKETED.sub(" ", str(title or ""))
    for word in _NOISE_WORDS:
        text = text.replace(word, " ")
    return "".join(text.split())[:_QUERY_MAX]


async def _shells(
    ctx: RunContext,
    *,
    platform: str,
    keyword: str,
    exclude: str = "",
    issues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """搜同款，返回按 ``item_id`` 去重后的列表壳；搜失败返回 ``(空, 错误码)``。

    壳负责价格基线（价差就是拿它算的）与竞争条数；需求数只有详情才有。

    ``exclude`` 是本商品自己的 id —— 在这里剔掉，同款的详情预算才不会浪费在
    「已经有详情了」的那一条上。``appraise_item`` 内部还会再剔一次（幂等）。
    """
    search = await search_items(ctx, platform, keyword, _SEARCH_LIMIT)
    if not search.get("ok"):
        code = str(search.get("error_code") or "crawler.failed")
        issues.append(_issue(code, str(search.get("message") or "")))
        return [], code

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in search.get("items") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("item_id") or row.get("url") or "").strip()
        if key and key != exclude and key not in seen:
            seen.add(key)
            rows.append(row)
    return rows, None


async def _attach_detail(
    ctx: RunContext,
    *,
    platform: str,
    peers: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> bool:
    """给**下一条**还没拉过详情的同款补详情；返回是否补了。

    同 id 用详情**覆盖**壳而不是追加 —— 否则同一个商品会在同款表里出现两次，
    把竞争条数一起虚增。
    """
    target = next((row for row in peers if not row.get("_detailed")), None)
    if target is None:
        return False

    # 先打标再拉：拉失败也算「试过了」，否则预算会被同一条反复吃掉。
    target["_detailed"] = True
    item_id = str(target.get("item_id") or "").strip()
    if not item_id:
        return True

    detail = await fetch_detail(
        ctx,
        platform,
        item_id,
        xsec_token=target.get("xsec_token"),
        url=target.get("url"),
    )
    if not detail.get("ok"):
        code = str(detail.get("error_code") or "crawler.failed")
        issues.append(_issue(code, f"同款 {item_id} 详情没拉到"))
        return True

    for row in detail.get("items") or []:
        if not isinstance(row, dict):
            continue
        replace_at = next(
            (index for index, existing in enumerate(peers) if str(existing.get("item_id") or "") == item_id),
            None,
        )
        if replace_at is not None:
            row["_detailed"] = True
            peers[replace_at] = row
    return True


def _first_item(result: dict[str, Any]) -> dict[str, Any] | None:
    for row in result.get("items") or []:
        if isinstance(row, dict):
            return row
    return None


def _over_budget(started: float) -> bool:
    return time.monotonic() - started > _DEADLINE_S


def _issue(code: str, message: str) -> dict[str, Any]:
    return {"error_code": code, "message": message}


def _fail(plat: str, code: str, message: str) -> dict[str, Any]:
    """失败出参：形状与成功时对齐，只多 ``ok`` / ``error_code`` / ``message``。"""
    return {
        "ok": False,
        "kind": "product_appraisal",
        "target": None,
        "comparables": [],
        "error_code": code,
        "message": f"{plat or '鉴定'}：{message}",
    }


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="appraise_item",
        label="鉴定 · {platform}",
        description=(
            "用户给了一个**具体商品**（链接或 id）问「值不值得买 / 买来转卖划不划算」时调它。"
            "它会拉本商品详情、搜一批同款、给其中几条补详情，再按价差空间 / 需求热度 / "
            "竞争密度 / 售出验证下判词。\n"
            "回报里 verdict 只有四种（worth / caution / skip / insufficient），别自己改口径；"
            "comparables 是按价格升序的同款表，其中 is_target 为 true 的那行是**本商品自己**；"
            "evidence_gaps 写着「没量到」的维度，汇报时必须如实说「这项没量到」。"
        ),
        args=AppraiseInput,
        fn=appraise_item_tool,
        browser=True,
    ),
)
