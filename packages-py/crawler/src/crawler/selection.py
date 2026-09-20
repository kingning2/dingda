"""选品打分：把抓到的商品行折算成候选品类的确定性评分与理由。

职责：
    给「该卖什么」一个可复算的答案。输入是若干候选关键词各自的抓取结果
   （``agent.items.DetailItem`` 的 dict），输出是每个候选的度量、0~100 综合分、
   以及人类可读的理由。**不调用 LLM，不发网络请求。**

设计说明：
    - **输入是 ``DetailItem``，不是 ``CrawlItem``**：agent 层的 ``tools/crawl._ok`` 在
      边界上就把 ``CrawlItem.raw`` 丢掉了（只透 ``item_from_row`` 映射过的字段），
      所以打分器够不着 ``raw``。这既是限制也是好事 —— ``DetailItem`` 同时是前端
      解析的同一份真源，分数和界面看到的数是同一批。
    - **跨平台与诚实性规则住在 ``crawler.scoring``**：角色表（``EVIDENCE_ROLES``）、
      覆盖率打折的加权（``weighted``）、``unknown`` 哨兵判定都在那边，与单品鉴定
      （``crawler.appraisal``）共用一份 —— 复制会漂移。
    - **这里只管「候选之间怎么比」**：在同一个平台组内把需求/价格归一成可比的分数。
      组内区分不开的维度直接剔出，不给大家算 0 分。
"""

from __future__ import annotations

import logging
from typing import Any, Final

from contracts.watch import SoldState, is_finished
from crawler.scoring import (
    _DEFAULT_PLATFORM,
    demand_signal,
    entry_score,
    fmt_price,
    has_state_role,
    parse_count,
    quantile,
    state_of,
    weighted,
)

logger = logging.getLogger("dingda.crawler.selection")

# 各维度权重；样本不足的维度会被剔出并把权重归一，所以这些数只表达相对重要性。
WEIGHTS: Final[dict[str, float]] = {
    "demand": 40.0,
    "competition": 30.0,
    "entry": 20.0,
    "sold": 10.0,
}

# 竞争密度：结果条数越多说明这个赛道越挤。超过这个条数就按最挤算。
_CROWDED_AT = 40

# 判定「售出验证」需要的最少样本：n 太小的话售出比例没有意义。
_MIN_SAMPLE_FOR_SOLD = 3


def build_candidate(
    *,
    keyword: str,
    platform: str,
    items: list[dict[str, Any]],
    evidence_status: str = "measured",
) -> dict[str, Any]:
    """把一个候选关键词的抓取结果折成一份度量。

    ``items`` 是 ``DetailItem`` 的 dict 列表（可能混了列表壳与详情，字段多为空）。
    """
    prices = [value for value in (parse_count(item.get("price")) for item in items) if value]
    sellers = {
        str(item.get("seller_nick") or "").strip()
        for item in items
        if str(item.get("seller_nick") or "").strip()
    }
    states = [state_of(item.get("sold_state")) for item in items]
    known = [state for state in states if state]
    sold = sum(1 for state in known if is_finished(state))
    on_sale = sum(1 for state in known if state == SoldState.ON_SALE)

    candidate: dict[str, Any] = {
        "keyword": keyword,
        "platform": platform,
        "score_scope": platform,
        "sample_size": len(items),
        "detail_size": sum(1 for item in items if item.get("want_count") or item.get("browse_count")),
        "distinct_sellers": len(sellers),
        "price_p25": quantile(prices, 0.25),
        "price_median": quantile(prices, 0.5),
        "price_p75": quantile(prices, 0.75),
        "demand_total": demand_signal(platform, items),
        "sold_count": sold,
        "on_sale_count": on_sale,
        "state_known": len(known),
        "availability": "unverified",
        "evidence_status": evidence_status if items else "failed",
        "score": None,
        "evidence_coverage": None,
        "reasons": [],
        "evidence_gaps": [],
    }
    return candidate


def score_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """给候选打分并排序；返回新列表，``sample_size == 0`` 的候选被排除。

    归一化按平台分组进行 —— 分数只在同一平台内可比。
    """
    usable = [item for item in candidates if int(item.get("sample_size") or 0) > 0]
    dropped = len(candidates) - len(usable)
    if dropped:
        logger.info("选品排除无样本候选 count=%s", dropped)
    if not usable:
        return []

    scored: list[dict[str, Any]] = []
    for platform in {str(item.get("platform") or _DEFAULT_PLATFORM) for item in usable}:
        group = [item for item in usable if str(item.get("platform") or _DEFAULT_PLATFORM) == platform]
        scored.extend(_score_group(group))
    # 先按分数降序，再按平台名稳定分组，避免同分时顺序漂移。
    scored.sort(key=lambda item: (str(item.get("platform") or ""), -(item.get("score") or 0.0)))
    return scored


def _score_group(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """平台内的候选互相归一后打分。

    归一化需要一个**对比集**：一个维度如果在本组内区分不开（只有一个候选，
    或者大家的值全一样），它对排序没有信息量，直接剔出而不是给大家算 0 分 ——
    否则那部分权重会平白拖低所有人，让人误以为「量过且很差」。
    """
    platform = str(group[0].get("platform") or _DEFAULT_PLATFORM) if group else _DEFAULT_PLATFORM
    demands = [item.get("demand_total") for item in group]
    measured_demands = [value for value in demands if value]
    max_demand = max(measured_demands, default=0)
    demand_comparable = len(measured_demands) >= 2

    prices = [float(item["price_median"]) for item in group if item.get("price_median")]
    cheapest = min(prices) if prices else None
    ceiling = max(prices) if prices else None
    entry_comparable = len(set(prices)) >= 2

    out: list[dict[str, Any]] = []
    for item in group:
        parts: dict[str, float] = {}
        reasons: list[str] = []
        gaps: list[str] = []

        demand = item.get("demand_total")
        if demand is None:
            gaps.append("需求热度：该平台这个候选没量到想要/收藏数")
        elif not demand_comparable:
            gaps.append("需求热度：同平台没有对比候选，无法归一")
        else:
            parts["demand"] = demand / max_demand
            reasons.append(f"需求热度 {demand}（同平台最高 {max_demand}）")

        size = int(item.get("sample_size") or 0)
        # 条数越多越挤：按 _CROWDED_AT 截顶后取反。绝对刻度，不需要对比集。
        crowded = min(size, _CROWDED_AT) / _CROWDED_AT
        parts["competition"] = 1.0 - crowded
        sellers = int(item.get("distinct_sellers") or 0)
        reasons.append(f"竞争密度 样本 {size} 条 / {sellers} 个卖家")

        price = item.get("price_median")
        if not price:
            gaps.append("入手门槛：没量到价格")
        elif not entry_comparable:
            gaps.append("入手门槛：同平台价格无差异，无法比较")
        else:
            parts["entry"] = entry_score(float(price), cheapest, ceiling)
            reasons.append(
                f"入手门槛 中位价 ¥{fmt_price(price)}"
                f"（同平台 {fmt_price(cheapest)}~{fmt_price(ceiling)}）"
            )

        # 分母用「量到状态的条数」而不是样本总数：列表壳常常不带售出状态，
        # 拿总数当分母会把「没量到」算成「在售」，凭空压低售出比例。
        state_known = int(item.get("state_known") or 0)
        if not has_state_role(platform):
            gaps.append("售出验证：该平台不产出售出状态，这项无法量")
        elif state_known < _MIN_SAMPLE_FOR_SOLD:
            gaps.append(
                f"售出验证：量到售出状态的只有 {state_known} 条，不足 {_MIN_SAMPLE_FOR_SOLD} 条"
            )
        else:
            sold_count = int(item.get("sold_count") or 0)
            parts["sold"] = sold_count / state_known
            reasons.append(f"售出验证 已售/下架 {sold_count}/{state_known}")

        score, effective, coverage = weighted(parts, WEIGHTS)
        if not parts:
            gaps.append("全部维度都缺证据，不评分")
        out.append(
            {
                **item,
                "score": None if not parts else round(score, 1),
                "reasons": reasons,
                "evidence_gaps": gaps,
                "dimensions": {key: round(value, 3) for key, value in parts.items()},
                "weights_used": effective,
                "evidence_coverage": round(coverage, 2),
            }
        )
    return out
