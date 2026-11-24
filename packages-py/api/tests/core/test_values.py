"""core.values 空值归一帮手。"""

from __future__ import annotations

from core.values import as_dict, clean_text, optional_text


def test_clean_text_normalizes_none_and_whitespace() -> None:
    """None / 空串 / 纯空白都归一为 ""，其余去首尾空白。"""
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("   ") == ""
    assert clean_text("  x ") == "x"
    assert clean_text(0) == ""
    assert clean_text(123) == "123"
    assert clean_text({"a": 1}) == "{'a': 1}"


def test_optional_text_blanks_become_none() -> None:
    """空白归 None，非空去空白。"""
    assert optional_text(None) is None
    assert optional_text("  ") is None
    assert optional_text(" x ") == "x"


def test_as_dict_guards_non_dict() -> None:
    """非 dict 归空 dict，dict 原样透传。"""
    assert as_dict(None) == {}
    assert as_dict("bad") == {}
    assert as_dict([]) == {}
    d = {"k": "v"}
    assert as_dict(d) is d
