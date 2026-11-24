"""防御式取值帮手。

职责：
    收敛爬虫/渠道解析外部数据时反复出现的空值归一写法，
    避免每个文件各写一份 ``(x or "").strip()``。

设计说明：
    只服务「不可信外部输入」（DOM、平台 API、OCR），pydantic 校验过的
    输入不要再用这里设防（py-dev 第 1 节第 6 条）；不认识任何平台与业务。
    现有本地同名帮手（如 ali1688/compare.py 的 _clean_text）逐步向这里归拢。

使用示例::
    from core.values import as_dict, clean_text, optional_text

    clean_text(None) == ""
    clean_text("  x ") == "x"
    optional_text(" ") is None
    as_dict("bad").get("k") is None
"""
from __future__ import annotations

from typing import Any

__all__ = ["as_dict", "clean_text", "optional_text"]


def clean_text(value: Any) -> str:
    """任意值归一为去空白字符串：None/空 → ""。"""
    return str(value or "").strip()


def optional_text(value: Any) -> str | None:
    """同 clean_text，但空白归 None，适配「可空字段」语义。"""
    return clean_text(value) or None


def as_dict(value: Any) -> dict[str, Any]:
    """非 dict 归一为空 dict，替代 isinstance(x, dict) and x.get(...) 守卫。"""
    return value if isinstance(value, dict) else {}
