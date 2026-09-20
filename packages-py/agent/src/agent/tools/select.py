"""选品工具：把「该卖什么」变成一次可复算的搜索 + 打分。

职责：
    主编排拿到一个「我不知道该卖什么」的请求时调 ``select_products`` —— 给它几个
    候选品类关键词，它先给每个候选搜一遍、再按轮次给每个候选补几条详情，最后调
    ``crawler.selection`` 的确定性打分器排名，回报一张带理由的候选表。

设计说明：
    - **决策留在这里、打分不在这里**：提候选词是主编排的活（它才是拿主意的那层），
      算分是 ``crawler.selection`` 的活（纯函数、无 LLM）。工具只负责「按词取数 + 转交」，
      中间不掺任何判断 —— 所以答案里的每一个数都能倒着追到某次抓取。
    - **复用 ``agent.tools.crawl`` 的两个动作**，不自己开浏览器、不自己重试：
      ``search_items`` / ``fetch_detail`` 已经带了风控重试与 ``ok=False`` 语义，
      再写一遍只会多一条会腐烂的路径。
    - **上限卡在代码里，不写在提示词里**：``keywords`` / ``details_per_keyword`` 用
      pydantic 的 ``max_length`` / ``le`` 封顶，切片再兜一层。逐条详情很慢，模型每次
      都想多要几条，靠自觉是拦不住的。
    - **失败不炸穿**：单个候选撞风控只记一条 ``issues`` 并让该候选缺席，其余候选照常
      排名；全部失败才 ``ok=False``，``error_code`` 取出现最多的那个码。
    - **先铺便宜维度，再补贵的**：分两阶段 —— 先给**每个**候选搜一遍（条数即竞争密度，
      且搜索便宜），再按**轮次**发详情（一轮每个候选各补一条）。反过来按候选顺序发，
      第一个候选会吃光预算、后两个一条详情都没有：实测 3 个候选只有第 1 个出分，
      另外两个因超预算缺席，候选之间没得比，选品也就没得选。
    - **出参不带顶层 ``platform`` + ``items``**：前端 ``extractProducts`` 是看到这两个键
      就吃的，带上了会把候选表当成商品列表塞进商品面板。所以候选键叫 ``candidates``，
      平台放 ``platforms``（复数）。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

from crawler.selection import build_candidate, score_candidates
from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec
from agent.steps import platform_label
from agent.tools.crawl import fetch_detail, search_items

logger = logging.getLogger("dingda.agent.tool.select")

SUPPORTED_PLATFORMS: Final = ("xianyu", "xiaohongshu", "ali1688")

# 每个候选先搜这么多条做「竞争密度」的底样，再挑前几条拉详情补需求数。
_SEARCH_LIMIT = 30

# 整次选品的墙钟预算。逐条详情本身很慢（闲鱼详情走 mtop，实测 14~30s 一条，还要过
# `DINGDA_DETAIL_MIN_INTERVAL_S` 的节流闸门；撞风控要过滑块时一条能到 90s），所以这个
# 数看着大。它的职责是**兜住跑飞**，不是压缩正常路径 —— 正常路径靠 pydantic 的条数
# 上限收口。实测过没有这道闸会怎样：一个爬虫子 agent 连拉 44 条详情、跑了一个小时
# 还没停。
# 超预算不硬打断在跑的那次抓取，只在**下一条开抓之前**停手，剩下的候选标 partial。
# 实测校准：选品要量足 —— 3 词 × 3 条详情 + 搜索，正常要 5~10 分钟，两轮补量到
# 10 分钟以上很常见。300s 会把「看起来很快但量得浅」的结果当成品。
_DEADLINE_S = 900.0


class SelectInput(BaseModel):
    """选品入参。"""

    keywords: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "候选品类关键词，**最多 3 个**，每个都必须是你能说得出理由的具体品类"
            "（如「露营折叠桌」），不要写「热门商品」这种没有边界的词。"
        ),
    )
    platforms: list[str] = Field(
        default=["xianyu"],
        max_length=2,
        description=(
            "平台，最多 2 个。闲鱼数据最全（价格 + 需求数）；"
            "选品类请求建议再带上 xiaohongshu 交叉看内容热度。"
        ),
    )
    details_per_keyword: int = Field(
        default=3,
        ge=0,
        le=3,
        description="每个候选拉几条详情来量需求数与售出验证。详情很慢，但售出验证至少要 3 个样本，默认拉满 3 条。",
    )
    reason: str = Field(
        default="",
        description="一句话说明为什么挑这几个候选（给用户看的依据，不是给系统看的）。",
    )


async def select_products(
    ctx: RunContext,
    keywords: list[str],
    platforms: list[str] | None = None,
    details_per_keyword: int = 2,
    reason: str = "",
) -> dict[str, Any]:
    """按候选关键词逐个取数并排名，回报带理由的候选表。"""
    plats = _clean_platforms(platforms)
    words = [word.strip() for word in keywords if (word or "").strip()][:3]
    if not plats:
        return _fail(plats, "agent.invalid_input", "platforms 不能为空")
    if not words:
        return _fail(plats, "agent.invalid_input", "keywords 不能为空")

    per_word = max(0, min(int(details_per_keyword), 3))
    started = time.monotonic()
    units: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    partial = False

    # 阶段一：先给**每个**候选搜一遍。条数就是「竞争密度」，而且这一步便宜 ——
    # 先把便宜的维度铺满，再拿剩下的预算补贵的那部分（详情）。
    for platform in plats:
        for keyword in words:
            if ctx.cancelled():
                partial = True
                issues.append(_issue(platform, keyword, "agent.cancelled", "运行被取消"))
                break
            if _over_budget(started):
                partial = True
                issues.append(_deadline_issue(platform, keyword))
                break

            rows, failure = await _shells(ctx, platform=platform, keyword=keyword, issues=issues)
            if not rows:
                # 搜挂了、搜到空：都进 excluded 并带上原因，
                # 让模型看得见「这个词没量到」而不是以为它不存在。
                excluded.append(
                    {
                        "keyword": keyword,
                        "platform": platform,
                        "error_code": failure or "crawler.empty",
                    }
                )
                continue
            units.append({"platform": platform, "keyword": keyword, "rows": rows, "detailed": set()})
        if partial:
            break

    # 阶段二：详情**按轮次**发，一轮每个候选各补一条。宁可三个候选各量到一条，
    # 也不要第一个吃满两条、后两个一条没有 —— 候选之间要能比，才谈得上「选」。
    # 实测就是这么翻车的：顺序发详情时 3 个候选只有第 1 个够到分，另外两个因超预算
    # 缺席，`demand` / `entry` 两个维度全被剔掉，最后给用户一个 7.5 分、覆盖率 30% 的
    # 单候选「结论」。
    stopped = False
    for _round in range(per_word):
        for unit in units:
            if ctx.cancelled():
                partial, stopped = True, True
                issues.append(
                    _issue(str(unit["platform"]), str(unit["keyword"]), "agent.cancelled", "运行被取消")
                )
                break
            if _over_budget(started):
                partial, stopped = True, True
                issues.append(_deadline_issue(str(unit["platform"]), str(unit["keyword"])))
                break
            await _attach_detail(ctx, unit=unit, issues=issues)
        if stopped:
            break

    for unit in units:
        candidates.append(
            build_candidate(
                keyword=str(unit["keyword"]),
                platform=str(unit["platform"]),
                items=list(unit["rows"]),
            )
        )

    ranked = score_candidates(candidates)
    logger.info(
        "选品完成 run=%s 平台=%s 候选=%s 出分=%s 排除=%s 用时=%.1fs",
        ctx.run_id,
        ",".join(plats),
        len(candidates),
        len(ranked),
        len(excluded),
        time.monotonic() - started,
    )

    if not ranked:
        code = _dominant_code(issues) or "crawler.failed"
        return {
            "ok": False,
            "kind": "product_selection",
            "platforms": plats,
            "candidates": [],
            "excluded": excluded,
            "issues": issues,
            "partial": partial,
            "error_code": code,
            "message": f"{_fail_label(plats)}：候选都没取到可用样本，选品给不出结论",
        }

    return {
        "ok": True,
        "kind": "product_selection",
        "platforms": plats,
        "candidates": ranked,
        "excluded": excluded,
        "issues": issues,
        "partial": partial,
        "reason": reason.strip(),
        "message": _summary(ranked, excluded, partial),
    }


async def _shells(
    ctx: RunContext,
    *,
    platform: str,
    keyword: str,
    issues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """搜一个词，返回按 ``item_id`` 去重后的列表壳；失败返回 ``(空, 错误码)``。

    壳负责「竞争密度」（条数就是拥挤程度）与价格带 —— 这两样列表页就有。
    真正只有详情才给的（需求热度 / 售出）留到 ``_attach_detail`` 补。
    """
    search = await search_items(ctx, platform, keyword, _SEARCH_LIMIT)
    if not search.get("ok"):
        code = str(search.get("error_code") or "crawler.failed")
        issues.append(_issue(platform, keyword, code, str(search.get("message") or "")))
        return [], code

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in search.get("items") or []:
        if not isinstance(row, dict):
            continue
        key = _row_key(row)
        if key and key not in seen:
            seen.add(key)
            rows.append(row)
    return rows, None


async def _attach_detail(
    ctx: RunContext,
    *,
    unit: dict[str, Any],
    issues: list[dict[str, Any]],
) -> bool:
    """给一个候选补**一条**它还没拉过的详情；返回是否补上。

    详情比壳全（需求数 / 售出状态只有详情页有），同 id 用详情**覆盖**壳而不是追加 ——
    否则同一个商品会在样本里出现两次，把竞争密度和人头数一起虚增。
    """
    platform = str(unit["platform"])
    keyword = str(unit["keyword"])
    rows: list[dict[str, Any]] = unit["rows"]
    done: set[str] = unit["detailed"]

    target = next((row for row in rows if _row_key(row) not in done), None)
    if target is None:
        return False
    item_id = str(target.get("item_id") or "").strip()
    if not item_id:
        done.add(_row_key(target))
        return False
    done.add(item_id)

    detail = await fetch_detail(
        ctx,
        platform,
        item_id,
        xsec_token=target.get("xsec_token"),
        url=target.get("url"),
    )
    if not detail.get("ok"):
        code = str(detail.get("error_code") or "crawler.failed")
        issues.append(_issue(platform, keyword, code, str(detail.get("message") or "")))
        return False

    for row in detail.get("items") or []:
        if not isinstance(row, dict):
            continue
        replace_at = next(
            (index for index, existing in enumerate(rows) if _row_key(existing) == item_id),
            None,
        )
        if replace_at is None:
            rows.append(row)
        else:
            rows[replace_at] = row
    return True


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("item_id") or row.get("url") or "")


def _over_budget(started: float) -> bool:
    return time.monotonic() - started > _DEADLINE_S


def _deadline_issue(platform: str, keyword: str) -> dict[str, Any]:
    return _issue(
        platform, keyword, "agent.deadline", f"超出 {_DEADLINE_S:.0f}s 预算，剩余候选未取数"
    )


def _clean_platforms(platforms: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in platforms or ["xianyu"]:
        plat = str(raw or "").strip().lower()
        if plat in SUPPORTED_PLATFORMS and plat not in out:
            out.append(plat)
    return out[:2]


def _issue(platform: str, keyword: str, code: str, message: str) -> dict[str, Any]:
    return {
        "platform": platform,
        "keyword": keyword,
        "error_code": code,
        "message": message,
    }


def _dominant_code(issues: list[dict[str, Any]]) -> str | None:
    """出现最多的失败码 —— 全失败时用它当主因。"""
    if not issues:
        return None
    counts: dict[str, int] = {}
    for issue in issues:
        code = str(issue.get("error_code") or "")
        if code:
            counts[code] = counts.get(code, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda code: counts[code])


def _fail_label(plats: list[str]) -> str:
    return " / ".join(platform_label(plat) for plat in plats) or "选品"


def _summary(
    ranked: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    partial: bool,
) -> str:
    top = ranked[0]
    text = (
        f"量到 {len(ranked)} 个候选，最高分是「{top['keyword']}」"
        f"（{top['score']} 分，{platform_label(str(top.get('platform') or ''))}）"
    )
    if excluded:
        text += f"；{len(excluded)} 个候选没取到样本"
    if partial:
        text += "；预算用完，结果不完整"
    return text


def _fail(plats: list[str], code: str, message: str) -> dict[str, Any]:
    """失败出参：形状与成功时对齐，只多 ``error_code`` / ``message``。"""
    return {
        "ok": False,
        "kind": "product_selection",
        "platforms": plats,
        "candidates": [],
        "excluded": [],
        "issues": [],
        "partial": False,
        "error_code": code,
        "message": f"{_fail_label(plats)}：{message}",
    }


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="select_products",
        label="选品 · {platform}",
        description=(
            "用户不知道该卖什么时调它：给几个候选品类关键词，它会逐个去搜、各抓几条详情，"
            "再用确定性打分器按需求热度 / 竞争密度 / 入手门槛 / 售出验证排名，"
            "回报一张带理由的候选表。\n"
            "关键词最多 3 个，每个都要具体。回报里 candidates 是算过分的候选（含 score、"
            "reasons、evidence_gaps）；excluded 是没取到样本的（**不要**替它们下结论）。"
        ),
        args=SelectInput,
        fn=select_products,
        browser=True,
    ),
)
