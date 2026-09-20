"""打分公共件：字段角色表、计数解析、覆盖率打折加权、价格分位。

职责：
    给所有「把抓到的商品行折算成分数」的打分器提供同一套底座 ——
    ``selection.py``（品类级选品）与 ``appraisal.py``（单品级鉴定）都建在它上面。
    纯函数、无 LLM、无网络、无平台 import（只认 ``contracts.watch`` 的状态常量）。

设计说明：
    - **为什么单独一个模块**：这里全是容易腐烂的细活 —— 跨平台字段名撞车的角色表、
      ``unknown`` 哨兵判定、覆盖率打折的加权公式。复制一份必然漂移，而那条
      「extractor 不再产出某个字段就报红」的护栏测试只能护住一份实现。
    - **跨平台字段名是撞的，角色表就是解药**：``want_count`` 在闲鱼是「想要人数」，
      在小红书是「收藏数」（``sources/xiaohongshu/extractor.py`` 把 ``collected`` 写进
      这个 key）；``browse_count`` 同理是「浏览量」对「点赞数」。**语义不同的量，
      直接相加会得出一个没有意义的数。** 所以平台差异只在这张表里分叉，计算里不分叉。
    - **只在平台内归一**：需求正则化以平台为界。跨平台的量本来就不可比，
      所以分数只在同一平台内可比，调用方要在出参里标明这件事。
    - **量不到的东西不算，不给 0**：见 ``weighted``。
"""

from __future__ import annotations

import re
from statistics import median
from typing import Any, Final

from contracts.watch import SoldState

# 证据角色：平台 → 角色 → DetailItem 上的字段名。
# 角色语义固定（want=想买的人数、save=收藏、like=点赞），平台实现不同。
# **只在平台真有这个量时登记**：小红书与 1688 的 extractor 从不产出 ``sold_state``，
# 挂上去只会让「售出验证」永远拿到 items.py 补的那个 ``unknown`` 哨兵、算出一个假 0。
ROLE_WANT: Final = "want"
ROLE_VIEW: Final = "view"
ROLE_SAVE: Final = "save"
ROLE_LIKE: Final = "like"
ROLE_PRICE: Final = "price"
ROLE_STATE: Final = "state"

EVIDENCE_ROLES: Final[dict[str, dict[str, str | None]]] = {
    "xianyu": {
        ROLE_WANT: "want_count",
        ROLE_VIEW: "browse_count",
        ROLE_PRICE: "price",
        ROLE_STATE: "sold_state",
    },
    "xiaohongshu": {
        # 注意：这两个 key 名字与闲鱼相同，但语义是收藏/点赞，不是想要/浏览。
        ROLE_SAVE: "want_count",
        ROLE_LIKE: "browse_count",
        ROLE_PRICE: None,
    },
    "ali1688": {
        ROLE_PRICE: "price",
    },
}

_DEFAULT_PLATFORM: Final = "xianyu"

# 需求侧角色：算「有多少人要」时要看的角色（价格与状态不在其中）。
_DEMAND_ROLES: Final = (ROLE_WANT, ROLE_SAVE, ROLE_LIKE)


def demand_signal(platform: str, items: list[dict[str, Any]]) -> int | None:
    """单个平台内的需求原始聚合；该平台无量出的需求字段时返回 ``None``。

    **只在平台内算**：调用方拿到的是「这个候选在这个平台上」的需求量，
    不是跨平台可比的绝对数。跨平台相加没有意义（见模块 docstring）。
    """
    roles = EVIDENCE_ROLES.get(platform)
    if not roles:
        return None
    total = 0
    measured = False
    for role in _DEMAND_ROLES:
        field = roles.get(role)
        if not field:
            continue
        for item in items:
            count = parse_count(item.get(field))
            if count is None:
                continue
            measured = True
            total += count
    # 闲鱼的「浏览」量级远大于「想要」，但同平台内的候选是同一把尺子，
    # 比的是排序而不是绝对值，所以并列相加是可接受的。
    view_field = roles.get(ROLE_VIEW)
    if view_field:
        for item in items:
            count = parse_count(item.get(view_field))
            if count is None:
                continue
            measured = True
            total += count
    return total if measured else None


def weighted(
    parts: dict[str, float],
    weights: dict[str, float],
) -> tuple[float, dict[str, float], float]:
    """按可用维度加权，**再按证据覆盖率打折**；返回 ``(分数, 生效权重, 覆盖率)``。

    两件事，缺一不可：

    1. 缺的维度剔出、权重重新归一 —— 不给 0 分（0 分和「量过且很差」分不开）。
    2. 但归一化会**奖励证据稀薄的候选**：只剩「竞争密度」一个维度时它自己就是
       满分，会盖过「四个维度都量到、只是都不拔尖」的候选。所以最终分数再乘上
       覆盖率（量到的权重 / 全部权重）—— **知道得少，分就该低**。

    ``weights`` 由调用方给：选品与鉴定看重的维度不同，所以它是入参不是常量。
    """
    available = {key: weights[key] for key in parts if key in weights}
    total_weight = sum(weights.values())
    measured_weight = sum(available.values())
    if measured_weight <= 0:
        return 0.0, {}, 0.0
    effective = {key: value / measured_weight for key, value in available.items()}
    quality = sum(parts[key] * effective[key] for key in effective)
    coverage = measured_weight / total_weight
    return quality * coverage * 100, {key: round(value, 3) for key, value in effective.items()}, coverage


def entry_score(price: float, cheapest: float | None, ceiling: float | None) -> float:
    """入手门槛：同平台内越便宜越好（零基础卖家本金有限）。

    只在 ``cheapest ~ ceiling`` 之间线性铺开：最便宜满分、最贵 0 分。用相对位置
    而不是绝对价格，因为「贵」是相对于同批候选而言的。两者相等时不该调用 ——
    没有差异就没有信息量，调用方会把这个维度剔出。
    """
    if not cheapest or not ceiling or ceiling <= cheapest:
        return 0.0
    span = ceiling - cheapest
    return max(0.0, min(1.0, 1.0 - (price - cheapest) / span))


def parse_count(value: Any) -> int | None:
    """中文计数文案 → int；认不出返回 ``None``（不猜）。

    上游会把「1.2万」「3万+」「¥19.99」「1,234」都塞进同一个字段位，
    所以这里既剥符号也认万/亿后缀。
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    number = float(match.group(1))
    if "亿" in text:
        number *= 100_000_000
    elif "万" in text:
        number *= 10_000
    return int(number)


def has_state_role(platform: str) -> bool:
    """该平台是否真的产出售出状态（只有闲鱼有）。"""
    return bool((EVIDENCE_ROLES.get(platform) or {}).get(ROLE_STATE))


def state_of(value: Any) -> str | None:
    """售出状态规范化；``unknown`` 与空值都算「没量到」。

    ``agent.items.item_from_row`` 对缺失的 ``sold_state`` 会补一个 ``SoldState.UNKNOWN``
    哨兵，所以这里必须把 ``unknown`` 也当成缺测 —— 否则小红书那些从不产出状态的候选
    会被算成「量到 3 条、售出 0 条」，凭空得一个假 0 分。
    """
    text = str(value or "").strip().lower()
    if not text or text == SoldState.UNKNOWN:
        return None
    return text


def quantile(values: list[float], fraction: float) -> float | None:
    """样本分位（小样本用插值线性近似）；空样本返回 ``None``。"""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = fraction * (len(ordered) - 1)
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def fmt_price(value: Any) -> str:
    """价格文案：整数不带小数点，否则两位。"""
    number = float(value)
    return str(int(number)) if number == int(number) else f"{number:.2f}"


def median_of(values: list[float]) -> float | None:
    """跨平台价格中位（仅诊断用，不参与打分）。"""
    return median(values) if values else None
