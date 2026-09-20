"""鉴定打分单测：价差是硬否决、同款不串味、没量到的不给 0。

打分器是纯函数，这里不碰网络、不碰浏览器。重点断言围着一个问题：
**判词能不能倒着追到真实抓到的数上**。所以重点测两件事 —— 价差不许被别的维度
补偿，以及没量到的东西不会被编成数。
"""

from __future__ import annotations

import json

from crawler.appraisal import (
    VERDICT_CAUTION,
    VERDICT_INSUFFICIENT,
    VERDICT_SKIP,
    VERDICT_WORTH,
    _MIN_SPREAD,
    appraise_item,
    margin_score,
    price_spread,
)

_TARGET = {
    "item_id": "t",
    "title": "露营折叠桌",
    "price": "10",
    "want_count": "200",
    "browse_count": "2000",
    "sold_state": "on_sale",
    "seller_nick": "我",
}

_PEERS = [
    {"item_id": "a", "title": "同款甲", "price": "40", "want_count": "5", "browse_count": "50", "sold_state": "on_sale", "seller_nick": "甲"},
    {"item_id": "b", "title": "同款乙", "price": "50", "want_count": "4", "browse_count": "40", "sold_state": "on_sale", "seller_nick": "乙"},
    {"item_id": "c", "title": "同款丙", "price": "60", "want_count": "3", "browse_count": "30", "sold_state": "on_sale", "seller_nick": "丙"},
]


def _appraise(target: dict, peers: list[dict], platform: str = "xianyu") -> dict:
    return appraise_item(platform=platform, target=target, comparables=peers)


def test_price_spread_signs() -> None:
    """低于同款为正、高于同款为负；任一侧缺失或中位为 0 一律 None（不硬算）。"""
    assert price_spread(10, 50) == 0.8
    assert price_spread(100, 50) == -1.0
    assert price_spread(None, 50) is None
    assert price_spread(10, None) is None
    assert price_spread(10, 0) is None


def test_margin_score_is_clamped_linear() -> None:
    """比同款贵两成得 0 分、便宜四成满分；同价落在 1/3 —— 没被宰但也没空间。"""
    assert margin_score(-0.20) == 0.0
    assert margin_score(-0.50) == 0.0
    assert margin_score(0.40) == 1.0
    assert margin_score(1.0) == 1.0
    assert round(margin_score(0.0), 3) == 0.333


def test_target_inside_comparables_does_not_flatten_the_spread() -> None:
    """同款集里混进本商品自己时，价差必须还是一样的 —— 剔自身是幂等的。

    不剔的话中位价被自己拉平、价差恒为 0，症状是「所有商品都判不值得」：
    一个不报错但全错的静默故障。
    """
    clean = _appraise(_TARGET, list(_PEERS))
    polluted = _appraise(_TARGET, [*_PEERS, dict(_TARGET)])

    assert clean["price_median"] == 50
    assert clean["spread"] == 0.8
    assert polluted["spread"] == clean["spread"]
    assert polluted["price_median"] == clean["price_median"]
    assert polluted["verdict"] == clean["verdict"]


def test_demand_cannot_compensate_a_missing_spread() -> None:
    """比同款贵一倍、需求再爆表，判词也必须是不值得 —— 价差是硬否决。"""
    dear = {**_TARGET, "price": "100", "want_count": "99999", "browse_count": "999999"}
    out = _appraise(dear, list(_PEERS))

    assert out["spread"] == -1.0
    assert out["dimensions"]["demand"] == 1.0, "需求确实量到了满分，只是不能抵消价差"
    assert out["verdict"] == VERDICT_SKIP
    assert out["verdict_label"] == "不值得"
    assert "贵" in out["verdict_reason"]


def test_tiny_spread_is_not_a_business() -> None:
    """只比同款便宜 2% 也算不值得：这点价差不够转卖。"""
    out = _appraise({**_TARGET, "price": "49"}, list(_PEERS))

    assert 0 <= out["spread"] < _MIN_SPREAD
    assert out["verdict"] == VERDICT_SKIP


def test_small_spread_is_not_worth_buying() -> None:
    """【回归】5%~15% 的毛价差**不判值得买** —— 价差地板是 15%，不是 5%。

    这是实测调过的阈值：中位价 ¥50 时买 ¥47（便宜 6%）原本判「值得买」，理由是
    「有转卖空间」。但 15% 以下扣掉闲鱼手续费、运费与压货时间就不是生意，
    对一个要 agent 替他决策的用户，那句话是误导。
    """
    out = _appraise({**_TARGET, "price": "45"}, list(_PEERS))  # 便宜 10%

    assert 0.05 < out["spread"] < _MIN_SPREAD
    assert out["verdict"] == VERDICT_SKIP
    assert out["verdict_label"] == "不值得"
    assert "不够转卖" in out["verdict_reason"]

    # 刚过地板就是值得买 —— 说明拦住它的是价差，不是分不够
    just_over = _appraise({**_TARGET, "price": "42"}, list(_PEERS))  # 便宜 16%
    assert just_over["spread"] > _MIN_SPREAD
    assert just_over["verdict"] == VERDICT_WORTH


def test_no_comparables_does_not_hand_out_a_mark() -> None:
    """【回归】同款集为空时竞争密度进缺口，不许拿满分。

    ``1 - min(0, _CROWDED_AT)/_CROWDED_AT = 1.0`` —— 一个没量到的维度却进了
    ``dimensions``，还把覆盖率凭空垫高 20%。「一条同款都没搜到」不是「一点都不挤」。
    """
    out = _appraise(_TARGET, [])

    assert "competition" not in out["dimensions"]
    assert out["weights_used"] == {}
    assert out["evidence_coverage"] == 0.0
    assert any("竞争密度" in gap for gap in out["evidence_gaps"])


def test_missing_sellers_is_not_reported_as_zero_sellers() -> None:
    """【回归】卖家字段整批缺失时只说条数 —— 写「0 个卖家」会被读成「没有卖家」。"""
    bare = [{key: value for key, value in row.items() if key != "seller_nick"} for row in _PEERS]
    out = _appraise(_TARGET, bare)

    competition = next(reason for reason in out["reasons"] if reason.startswith("竞争密度"))
    assert "0 个卖家" not in competition
    assert "没量到" in competition
    assert out["distinct_sellers"] == 0


def test_clear_spread_with_evidence_is_worth() -> None:
    """明显低于同款中位价 + 四个维度都量到 → 值得买。"""
    out = _appraise(_TARGET, list(_PEERS))

    assert out["spread"] == 0.8
    assert out["evidence_coverage"] == 1.0
    assert out["score"] == 87.0
    assert out["verdict"] == VERDICT_WORTH
    assert out["verdict_label"] == "值得买"


def test_no_comparable_price_is_insufficient_not_a_low_score() -> None:
    """同款一条价格都没有 → 判不了，且**不给分**（给 0 会被读成「量过且很差」）。"""
    peers = [{key: value for key, value in row.items() if key != "price"} for row in _PEERS]
    out = _appraise(_TARGET, peers)

    assert out["verdict"] == VERDICT_INSUFFICIENT
    assert out["verdict_label"] == "判不了"
    assert out["score"] is None
    assert out["spread"] is None
    assert any("价差空间" in gap for gap in out["evidence_gaps"])


def test_1688_demand_is_never_invented() -> None:
    """1688 的角色表里没有需求项 —— 就算行里带着 want_count 也不许算出需求分。

    这正是跨平台「串味」的形状：字段名恰好存在，但那个平台根本量不出这个量。
    """
    out = _appraise(_TARGET, list(_PEERS), platform="ali1688")

    assert "demand" not in out["dimensions"]
    assert any("需求热度" in gap for gap in out["evidence_gaps"])


def test_non_xianyu_state_is_not_measured() -> None:
    """小红书不产出售出状态，哪怕字段里写着 on_sale 也不算量到。"""
    out = _appraise(_TARGET, list(_PEERS), platform="xiaohongshu")

    assert "sold" not in out["dimensions"]
    assert any("不产出售出状态" in gap for gap in out["evidence_gaps"])


def test_unknown_sentinel_counts_as_unmeasured() -> None:
    """``items.py`` 给缺失状态补的 ``unknown`` 哨兵不算量到（只有闲鱼才有状态）。"""
    peers = [{**row, "sold_state": "unknown"} for row in _PEERS]
    out = _appraise(_TARGET, peers)

    assert out["state_known"] == 0
    assert "sold" not in out["dimensions"]
    assert any("不足" in gap for gap in out["evidence_gaps"])


def test_thin_evidence_scores_lower_than_measured_one() -> None:
    """证据稀薄不许靠「权重归一」反超量得全的 —— 覆盖率那一次乘法就是拦它的。"""
    bare = [{key: value for key, value in row.items() if key in {"item_id", "price"}} for row in _PEERS]
    thin = _appraise(_TARGET, bare)
    full = _appraise(_TARGET, list(_PEERS))

    assert thin["evidence_coverage"] < full["evidence_coverage"]
    assert thin["score"] < full["score"]
    assert thin["verdict"] == VERDICT_CAUTION


def test_comparable_table_is_price_sorted_with_target_in_place() -> None:
    """同款表按价格升序，本商品自己作为一行插在它的价格位置上、且相对差为 0。

    这一列的存在是为了回答转卖的第二半：**还有没有更便宜的同类**。
    """
    out = _appraise(_TARGET, list(_PEERS))
    rows = out["comparables"]

    prices = [float(row["price"]) for row in rows]
    assert prices == sorted(prices)
    assert prices == [10, 40, 50, 60]

    targets = [row for row in rows if row["is_target"]]
    assert len(targets) == 1
    assert targets[0]["item_id"] == "t"
    assert targets[0]["price_delta_pct"] == 0
    assert rows[1]["price_delta_pct"] == 300.0


def test_appraisal_is_json_serializable() -> None:
    """出参要能原样进 SSE（前端解析的就是这份），所以不能有非 JSON 类型。"""
    out = _appraise(_TARGET, list(_PEERS))
    assert json.loads(json.dumps(out, ensure_ascii=False))["verdict"] == VERDICT_WORTH


def test_appraisal_never_carries_top_level_platform() -> None:
    """顶层不许有 platform —— 前端 ``extractProducts`` 看到它就认领，商品面板会被污染。"""
    out = _appraise(_TARGET, list(_PEERS))

    assert "platform" not in out
    assert "items" not in out
    assert out["target"]["platform"] == "xianyu"
