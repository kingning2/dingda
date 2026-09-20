"""单品鉴定：把「这一件值不值得买」折成一个可复算的判词。

职责：
    给一个**具体商品**一个可复算的答案。输入是本商品一份 + 它的**同款集**一份
    （都是 ``agent.items.DetailItem`` 的 dict），输出是四态判词、0~100 综合分、
    人类可读的理由与缺口，外加一张按价格升序的同款表（本商品自己也在里面）。
    **不调用 LLM，不发网络请求。**

设计说明：
    - **参照系是「同款」，不是「品类」**：``crawler.selection`` 回答「哪个品类该卖」，
      跨的是候选关键词；这里回答「这一件该不该下手」，跨的是同款商品。粒度与参照系
      都不同，所以是两个打分器，不是一个打分器加参数。
    - **价差是唯一实质理由**：转卖赚的就是「买得比同款便宜」。批发成本拿不到
      （1688 没有详情接口，AK 也过期），所以价差只能相对**同平台同款的中位价**算。
      因此价差是**硬否决**，不许被一个高需求分补偿 —— 见 ``_verdict_of``。
    - **同款集必须已经剔掉本商品自己**：不剔的话中位价被自己拉平、价差恒为 0，
      判词永远「不值得」。这条由调用方保证，但 ``appraise_item`` 会**再剔一次**
      （按 item_id）—— 便宜一个幂等动作，换掉一整类静默错误。
    - **跨平台与诚实性规则住在 ``crawler.scoring``**：角色表、覆盖率打折的加权、
      ``unknown`` 哨兵判定都与选品共用一份，复制会漂移。
    - **出参不带顶层 ``platform``**：前端 ``extractProducts`` 看到 ``record.platform``
      是字符串就认领，会把鉴定载荷当成商品列表塞进商品面板。平台放 ``target`` 里、
      同款数组叫 ``comparables`` —— 靠命名结构性避开，不靠解析顺序侥幸。
"""

from __future__ import annotations

import logging
from typing import Any, Final

from contracts.watch import is_finished
from crawler.scoring import (
    demand_signal,
    fmt_price,
    has_state_role,
    parse_count,
    quantile,
    state_of,
    weighted,
)

logger = logging.getLogger("dingda.crawler.appraisal")

VERDICT_WORTH: Final = "worth"
VERDICT_CAUTION: Final = "caution"
VERDICT_SKIP: Final = "skip"
VERDICT_INSUFFICIENT: Final = "insufficient"

VERDICT_LABELS: Final[dict[str, str]] = {
    VERDICT_WORTH: "值得买",
    VERDICT_CAUTION: "谨慎",
    VERDICT_SKIP: "不值得",
    VERDICT_INSUFFICIENT: "判不了",
}

# 各维度权重；样本不足的维度会被剔出并把权重归一，所以这些数只表达相对重要性。
# 价差占四成 —— 它是转卖的唯一实质理由，其余三项是「这个价差能不能兑现」的旁证。
WEIGHTS: Final[dict[str, float]] = {
    "margin": 40.0,
    "demand": 30.0,
    "competition": 20.0,
    "sold": 10.0,
}

# 竞争密度：同款条数越多越挤。**这里用 20 而不是选品那边的 40** —— 同款搜索上限
# 是 30 条，40 会被打满，那 20% 的权重就变成对所有人都一样的死权重（选品侧实测
# 过这个坑）。20 在「冷门几件」到「爆款几十件」之间还区分得开。
_CROWDED_AT = 20

# 判定「售出验证」需要的最少样本：n 太小的话售出比例没有意义。
_MIN_SAMPLE_FOR_SOLD = 3

# 价差 → 分的线性映射：比同款贵两成得 0 分，比同款便宜四成得满分。
_MARGIN_FLOOR = -0.20
_MARGIN_CEIL = 0.40

# 判词阈值。价差地板 = 15%：**这是毛价差**，不含闲鱼手续费、运费与压货时间，
# 5% 这种量级扣完就不是一门生意，说明白了也不能判「值得买」。
_MIN_SPREAD = 0.15
_WORTH_SCORE = 60.0
_WORTH_COVERAGE = 0.5


def price_spread(target_price: float | None, comparable_median: float | None) -> float | None:
    """本商品比同款中位价低多少；任一侧没量到返回 ``None``。

    正值 = 买得比同款便宜（有转卖空间），负值 = 买得比同款贵。中位价为 0 时
    返回 ``None`` —— 除零在这里没有业务含义，不该硬算出一个数。
    """
    if target_price is None or comparable_median is None or comparable_median <= 0:
        return None
    return (comparable_median - target_price) / comparable_median


def margin_score(spread: float) -> float:
    """价差 → 0~1 分：``_MARGIN_FLOOR`` 及以下 0 分，``_MARGIN_CEIL`` 及以上满分。

    线性、可解释、不用魔法数：同价（spread=0）落在 0.33 —— 即「同价买进没有空间，
    但也没被宰」，剩下的分数靠需求与竞争补。
    """
    span = _MARGIN_CEIL - _MARGIN_FLOOR
    return max(0.0, min(1.0, (spread - _MARGIN_FLOOR) / span))


def appraise_item(
    *,
    platform: str,
    target: dict[str, Any],
    comparables: list[dict[str, Any]],
    query: str = "",
    partial: bool = False,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """给一个商品下判词；``comparables`` 是它的同款集（已尽量剔掉它自己）。

    ``target`` / ``comparables`` 的元素都是 ``DetailItem`` 的 dict，字段多为空。
    """
    issues = list(issues or [])
    target_id = str(target.get("item_id") or "").strip()
    # 再剔一次自己：调用方漏了的话中位价会被自己拉平、价差恒 0，
    # 症状是「所有人都判不值得」—— 一个不报错但全错的静默故障，值得幂等防一次。
    peers = [
        row
        for row in comparables
        if isinstance(row, dict) and str(row.get("item_id") or "").strip() != target_id
    ]

    target_price = parse_count(target.get("price"))
    prices = [value for value in (parse_count(row.get("price")) for row in peers) if value]
    median = quantile(prices, 0.5)
    spread = price_spread(target_price, median)

    parts: dict[str, float] = {}
    reasons: list[str] = []
    gaps: list[str] = []

    # 价差空间 —— 核心维度，也是判词的硬否决依据。
    if spread is None:
        gaps.append("价差空间：没量到同款价格，算不出价差")
    else:
        parts["margin"] = margin_score(spread)
        direction = "低" if spread >= 0 else "高"
        reasons.append(
            f"价差空间 同款中位价 ¥{fmt_price(median)}，本商品 ¥{fmt_price(target_price)}"
            f"（{direction} {abs(spread) * 100:.0f}%）"
        )

    # 需求热度 —— 本商品自己的想要/浏览，对同款里量到的最高值归一。
    target_demand = demand_signal(platform, [target])
    peer_demands = [value for value in (demand_signal(platform, [row]) for row in peers) if value]
    peak_demand = max(peer_demands, default=0)
    if target_demand is None:
        gaps.append("需求热度：本商品没量到想要/浏览数")
    elif len(peer_demands) < 2:
        gaps.append("需求热度：同款里量到需求的不足 2 条，无法归一")
    else:
        parts["demand"] = min(1.0, target_demand / peak_demand)
        reasons.append(f"需求热度 本商品 {target_demand}（同款最高 {peak_demand}）")

    # 竞争密度 —— 绝对刻度，不需要对比集。
    size = len(peers)
    sellers = {
        str(row.get("seller_nick") or "").strip()
        for row in peers
        if str(row.get("seller_nick") or "").strip()
    }
    if size == 0:
        # 一条同款都没搜到：不是「不挤」，是**没法量**。给 1.0 会让覆盖率凭空多
        # 20% —— 一个没量到的维度却进了 dimensions，正是本函数要避免的那件事。
        gaps.append("竞争密度：没搜到同款，竞争程度量不出来")
    else:
        parts["competition"] = 1.0 - min(size, _CROWDED_AT) / _CROWDED_AT
        reasons.append(_competition_reason(size, len(sellers)))

    # 售出验证 —— 分母是「同款里量到状态的条数」。生产上闲鱼详情常走 DOM 回落，
    # 那条路径不产 sold_state，所以这项大概率整项落空 —— 如实说，不编。
    states = [state_of(row.get("sold_state")) for row in peers]
    known = [state for state in states if state]
    sold = sum(1 for state in known if is_finished(state))
    if not has_state_role(platform):
        gaps.append("售出验证：该平台不产出售出状态，这项无法量")
    elif len(known) < _MIN_SAMPLE_FOR_SOLD:
        gaps.append(f"售出验证：量到售出状态的同款只有 {len(known)} 条，不足 {_MIN_SAMPLE_FOR_SOLD} 条")
    else:
        parts["sold"] = sold / len(known)
        reasons.append(f"售出验证 同款已售/下架 {sold}/{len(known)}")

    score, effective, coverage = weighted(parts, WEIGHTS)
    verdict, verdict_reason = _verdict_of(
        spread=spread,
        score=None if not parts else score,
        coverage=coverage,
    )

    rows = _comparable_rows(
        peers=peers,
        target=target,
        platform=platform,
        target_price=target_price,
        target_id=target_id,
    )

    logger.info(
        "鉴定完成 platform=%s item=%s 判词=%s 分=%s 覆盖=%.2f 同款=%s",
        platform,
        target_id,
        verdict,
        None if not parts else round(score, 1),
        coverage,
        size,
    )

    return {
        "kind": "product_appraisal",
        "query": query,
        # 判不了就不给分：没量到同款价格时，一个 0~100 的数会被读成「量过且很差」。
        "score": None if verdict == VERDICT_INSUFFICIENT or not parts else round(score, 1),
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "verdict_reason": verdict_reason,
        "evidence_coverage": round(coverage, 2),
        "dimensions": {key: round(value, 3) for key, value in parts.items()},
        "weights_used": effective,
        "reasons": reasons,
        "evidence_gaps": gaps,
        "target": _row(target, platform=platform, target_id=target_id, is_target=True),
        "comparables": rows,
        "spread": round(spread, 4) if spread is not None else None,
        "price_p25": quantile(prices, 0.25),
        "price_median": median,
        "price_p75": quantile(prices, 0.75),
        "sample_size": size,
        "detail_size": sum(1 for row in peers if row.get("want_count") or row.get("browse_count")),
        "distinct_sellers": len(sellers),
        "state_known": len(known),
        "sold_count": sold,
        "partial": partial,
        "issues": issues,
    }


def _competition_reason(size: int, sellers: int) -> str:
    """竞争密度的理由句。卖家字段整批缺失时只说条数。

    写「0 个卖家」会被读成「这些商品没有卖家」，而真相是「没量到卖家」——
    与面板上「没量到的字段显示 — 不是 0」是同一条约定。
    """
    if sellers == 0:
        return f"竞争密度 同款 {size} 条（卖家数没量到）"
    return f"竞争密度 同款 {size} 条 / {sellers} 个卖家"


def _verdict_of(*, spread: float | None, score: float | None, coverage: float) -> tuple[str, str]:
    """四态判词。顺序即优先级 —— 价差的硬否决排在分数之前。

    价差是转卖的唯一实质理由：一个需求爆表但比同款还贵的商品，买进来就是套在手里。
    所以这里先看价差，再看分 —— 不让「需求热度」把「没有价差」补偿掉。
    """
    if spread is None:
        return VERDICT_INSUFFICIENT, "没量到同款价格，价差算不出来，判不了值不值得买"
    if spread < _MIN_SPREAD:
        if spread <= 0:
            return VERDICT_SKIP, f"比同款中位价还贵 {abs(spread) * 100:.0f}%，买进来没有转卖空间"
        return VERDICT_SKIP, f"只比同款中位价低 {spread * 100:.0f}%，这点价差不够转卖"
    if score is not None and score >= _WORTH_SCORE and coverage >= _WORTH_COVERAGE:
        return VERDICT_WORTH, f"比同款中位价低 {spread * 100:.0f}%，需求也量到了，有转卖空间"
    if coverage < _WORTH_COVERAGE:
        return VERDICT_CAUTION, (
            f"比同款中位价低 {spread * 100:.0f}%，但只量到 {coverage * 100:.0f}% 的证据，"
            "判断依据不足"
        )
    return VERDICT_CAUTION, f"比同款中位价低 {spread * 100:.0f}%，但需求/竞争不支持，优势不明显"


def _comparable_rows(
    *,
    peers: list[dict[str, Any]],
    target: dict[str, Any],
    platform: str,
    target_price: int | None,
    target_id: str,
) -> list[dict[str, Any]]:
    """同款表：按价格升序，本商品自己作为一行插进它的价格位置上。

    这么排是为了直接回答转卖决策的第二半 —— **「还有没有更便宜的同类」**。
    看得到比本商品便宜的同款，就知道这个价还能再谈；看不到，才算真的便宜。
    没有价格的行走最后（不猜它的位置）。
    """
    rows = [_row(row, platform=platform, target_id=target_id) for row in peers]
    rows.append(_row(target, platform=platform, target_id=target_id, is_target=True))

    def sort_key(row: dict[str, Any]) -> tuple[int, float]:
        price = parse_count(row.get("price"))
        return (1, 0.0) if price is None else (0, float(price))

    rows.sort(key=sort_key)
    for row in rows:
        row["price_delta_pct"] = _delta_pct(parse_count(row.get("price")), target_price)
    return rows


def _delta_pct(price: int | None, target_price: int | None) -> float | None:
    """这一行相对本商品价高/低多少（百分比，正 = 比本商品贵）。"""
    if price is None or not target_price:
        return None
    return round((price - target_price) / target_price * 100, 1)


def _row(
    row: dict[str, Any],
    *,
    platform: str,
    target_id: str,
    is_target: bool = False,
) -> dict[str, Any]:
    """同款表一行；字段名对齐前端 ``DetailItem`` 的解析习惯。"""
    return {
        "item_id": str(row.get("item_id") or ""),
        "title": str(row.get("title") or ""),
        "price": "" if row.get("price") is None else str(row.get("price")),
        "platform": platform,
        "url": str(row.get("url") or ""),
        "seller_nick": row.get("seller_nick"),
        "image_url": row.get("image_url"),
        "want_count": row.get("want_count"),
        "browse_count": row.get("browse_count"),
        "sold_state": state_of(row.get("sold_state")),
        "is_target": is_target or str(row.get("item_id") or "") == target_id,
    }
