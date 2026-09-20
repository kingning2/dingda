"""选品打分单测：跨平台不串味、样本不足不算分、覆盖率打折。

打分器是纯函数，这里不碰网络、不碰浏览器。最值钱的几条断言都围着一个问题：
**分数能不能倒着追到某次真实抓取上**。所以重点测「没量到的东西不会被编成数」。
"""

from __future__ import annotations

import json
from pathlib import Path

from crawler.scoring import (
    EVIDENCE_ROLES,
    ROLE_LIKE,
    ROLE_SAVE,
    ROLE_VIEW,
    ROLE_WANT,
    demand_signal,
    parse_count,
)
from crawler.selection import build_candidate, score_candidates

_XY_ITEMS = [
    {"item_id": "a", "price": "30", "want_count": "120", "browse_count": "900", "sold_state": "sold", "seller_nick": "甲"},
    {"item_id": "b", "price": "40", "want_count": "80", "browse_count": "600", "sold_state": "on_sale", "seller_nick": "乙"},
    {"item_id": "c", "price": "25", "want_count": "50", "browse_count": "300", "sold_state": "on_sale", "seller_nick": "丙"},
]

_CHEAPER_ITEMS = [
    {"item_id": "d", "price": "12", "want_count": "40", "browse_count": "200", "sold_state": "sold", "seller_nick": "丁"},
    {"item_id": "e", "price": "9", "want_count": "35", "browse_count": "180", "sold_state": "sold", "seller_nick": "戊"},
    {"item_id": "f", "price": "15", "want_count": "20", "browse_count": "90", "sold_state": "sold", "seller_nick": "己"},
]


def _by_keyword(rows: list[dict], keyword: str) -> dict:
    return next(row for row in rows if row["keyword"] == keyword)


def test_score_only_comparable_within_a_platform() -> None:
    """同批里塞一个小红书巨量候选，闲鱼候选的分**必须一点不变**。

    小红书把「收藏数」写进 ``want_count``、「点赞数」写进 ``browse_count``，跟闲鱼的
    「想要 / 浏览」只是**键名撞车**，量纲根本不可比。只要归一化偷偷跨了平台，
    xhs 那几个 9999 就会把闲鱼候选压成 0 分 —— 这条断言就是拦它的。
    """
    xianyu = [
        build_candidate(keyword="露营折叠桌", platform="xianyu", items=_XY_ITEMS),
        build_candidate(keyword="车载收纳箱", platform="xianyu", items=_CHEAPER_ITEMS),
    ]
    alone = score_candidates(list(xianyu))

    xhs = build_candidate(
        keyword="小红书爆款",
        platform="xiaohongshu",
        items=[{"item_id": "z", "want_count": "99999", "browse_count": "888888", "sold_state": "on_sale"}],
    )
    together = score_candidates([*xianyu, xhs])

    for before in alone:
        after = _by_keyword(together, before["keyword"])
        assert after["score"] == before["score"], before["keyword"]
        assert after["dimensions"] == before["dimensions"]


def test_demand_signal_is_per_platform_roles() -> None:
    """同一份输入在不同平台的语义不同：闲鱼读 want/view，小红书读 save/like。"""
    rows = [{"want_count": "10", "browse_count": "100"}]
    assert demand_signal("xianyu", rows) == 110

    roles = EVIDENCE_ROLES["xiaohongshu"]
    assert roles[ROLE_SAVE] == "want_count"
    assert roles[ROLE_LIKE] == "browse_count"
    assert ROLE_WANT not in roles, "小红书没有「想要」这个量，不能挂到 want 角色上"


def test_evidence_roles_cover_extractor_keys() -> None:
    """回归护栏：打分器认的字段名必须还在 extractor 的实际产出里。

    小红的 ``collected`` / ``liked`` 被映射成 ``want_count`` / ``browse_count``；
    谁哪天改了那个映射，这条会红 —— 而不是等到线上打出一堆没有意义的数。
    """
    source = (
        Path(__file__).resolve().parents[3]
        / "crawler" / "src" / "crawler" / "sources" / "xiaohongshu" / "extractor.py"
    ).read_text(encoding="utf-8")
    produced = set(EVIDENCE_ROLES["xiaohongshu"].values()) - {None}
    for field in produced:
        assert f'"{field}":' in source, f"小红书 extractor 不再产出 {field} 了"


def test_empty_candidate_is_excluded_not_scored_zero() -> None:
    """样本为 0 的候选直接出局 —— 0 分和「量过且很差」长得一样，混在一起会误导。"""
    rows = score_candidates(
        [
            build_candidate(keyword="有样本", platform="xianyu", items=_XY_ITEMS),
            build_candidate(keyword="没样本", platform="xianyu", items=[]),
        ]
    )
    assert [row["keyword"] for row in rows] == ["有样本"]


def test_price_band_reported_and_entry_dropped_when_flat() -> None:
    """价格带照报；但同平台价格没有差异时「入手门槛」不算分（没有信息量）。"""
    flat = [
        build_candidate(
            keyword="甲",
            platform="xianyu",
            items=[{"price": "30", "want_count": "10", "sold_state": "sold"}],
        ),
        build_candidate(
            keyword="乙",
            platform="xianyu",
            items=[{"price": "30", "want_count": "20", "sold_state": "sold"}],
        ),
    ]
    scored = score_candidates(flat)
    assert all(row["price_median"] == 30 for row in scored)
    for row in scored:
        assert "entry" not in row["dimensions"]
        assert any("入手门槛" in gap for gap in row["evidence_gaps"])


def test_entry_prefers_the_cheaper_candidate() -> None:
    """价格铺得开时，越便宜入手门槛分越高（新手本金有限）。"""
    scored = score_candidates(
        [
            build_candidate(keyword="贵", platform="xianyu", items=_XY_ITEMS),
            build_candidate(keyword="便宜", platform="xianyu", items=_CHEAPER_ITEMS),
        ]
    )
    assert _by_keyword(scored, "便宜")["dimensions"]["entry"] == 1.0
    assert _by_keyword(scored, "贵")["dimensions"]["entry"] == 0.0


def test_sold_ratio_uses_known_states_only() -> None:
    """售出比例的分母是「量到状态的条数」—— 壳子不带状态时不算作在售。"""
    items = [
        {"price": "10", "sold_state": "sold"},
        {"price": "10", "sold_state": "on_sale"},
        {"price": "10", "sold_state": "sold"},
        {"price": "10"},  # 列表壳：没量到状态
    ]
    scored = score_candidates(
        [
            build_candidate(keyword="甲", platform="xianyu", items=items),
            build_candidate(keyword="乙", platform="xianyu", items=items[:1]),
        ]
    )
    row = _by_keyword(scored, "甲")
    assert row["state_known"] == 3
    assert row["dimensions"]["sold"] == round(2 / 3, 3)


def test_unknown_state_sentinel_counts_as_unmeasured() -> None:
    """``items.py`` 给缺失状态的条目补 ``unknown`` 哨兵 —— 那不算量到。

    不挡这个，小红书那些从不产出状态的候选会被算成「量到 3 条、售出 0 条」，
    凭空得一个假 0 分；而小红书压根没有「售出」这个概念。
    """
    rows = [{"price": "10", "sold_state": "unknown"} for _ in range(5)]
    scored = score_candidates(
        [
            build_candidate(keyword="甲", platform="xiaohongshu", items=rows),
            build_candidate(keyword="乙", platform="xiaohongshu", items=_XY_ITEMS),
        ]
    )
    row = _by_keyword(scored, "甲")
    assert row["state_known"] == 0
    assert "sold" not in row["dimensions"]
    assert any("不产出售出状态" in gap for gap in row["evidence_gaps"])


def test_thin_evidence_scores_lower_than_measured_one() -> None:
    """证据稀薄的候选不许靠「权重归一」反超量得全的候选。"""
    scored = score_candidates(
        [
            build_candidate(keyword="量得全", platform="xianyu", items=_XY_ITEMS),
            build_candidate(
                keyword="只量到条数",
                platform="xiaohongshu",
                items=[{"item_id": "z", "sold_state": "on_sale"}],
            ),
        ]
    )
    full = _by_keyword(scored, "量得全")
    thin = _by_keyword(scored, "只量到条数")
    assert full["evidence_coverage"] > thin["evidence_coverage"]
    assert full["score"] > thin["score"]


def test_candidate_without_any_dimension_is_unscored() -> None:
    """一个维度都量不到就不给分（``None``），而不是给 0 分装成「量过」。"""
    # 单人组 ⇒ 需求无法归一；没价格 ⇒ 门槛无从比较；状态不足 ⇒ 售出不算。
    scored = score_candidates(
        [build_candidate(keyword="只有条数", platform="xiaohongshu", items=[{"item_id": "z", "sold_state": "on_sale"}])]
    )
    # 竞争密度是绝对刻度，仍有分；这里验证的是「覆盖率只算量到的权重」。
    row = scored[0]
    assert row["evidence_coverage"] == 0.3
    assert "demand" not in row["dimensions"]
    assert "entry" not in row["dimensions"]
    assert "sold" not in row["dimensions"]


def test_availability_is_never_verified() -> None:
    """货源可得性本轮一律标未验证 —— 1688 的 AK 过期了，不许假装查过货源。"""
    row = build_candidate(keyword="甲", platform="xianyu", items=_XY_ITEMS)
    assert row["availability"] == "unverified"


def test_parse_count_handles_chinese_units_and_symbols() -> None:
    assert parse_count("1.2万") == 12000
    assert parse_count("3万+") == 30000
    assert parse_count("¥19.99") == 19
    assert parse_count("1,234") == 1234
    assert parse_count(None) is None
    assert parse_count("面议") is None
    assert parse_count(True) is None


def test_scored_candidates_are_json_serializable() -> None:
    """出参要能原样进 SSE（前端解析的就是这份），所以不能有非 JSON 类型。"""
    scored = score_candidates([build_candidate(keyword="甲", platform="xianyu", items=_XY_ITEMS)])
    assert json.loads(json.dumps(scored, ensure_ascii=False))[0]["keyword"] == "甲"


def test_view_role_only_exists_for_xianyu() -> None:
    """小红书把浏览量写进 browse_count 的位置，语义其实是点赞 —— 不能当浏览用。"""
    assert EVIDENCE_ROLES["xianyu"][ROLE_VIEW] == "browse_count"
    assert ROLE_VIEW not in EVIDENCE_ROLES["xiaohongshu"]
    assert EVIDENCE_ROLES["xiaohongshu"][ROLE_LIKE] == "browse_count"
