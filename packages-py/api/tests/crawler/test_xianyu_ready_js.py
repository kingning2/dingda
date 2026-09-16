"""闲鱼就绪判据的防漂移单测（不启浏览器）。

``LIST_READY_JS`` / ``DETAIL_READY_JS`` 是纯 JS 字符串，靠 ``*_ready_arg()`` 把
``extract.json`` 的选择器喂进去。两处一旦对不上（字段改名、arg 漏字段），判据会
**静默恒为假** —— 症状是「白等满超时」，而不是报错，极难归因。这里把引用关系锁住。

行为验证（判据真能在页面上判对）见探针 ``api/scripts/probe_xianyu_ready_js.py``。
"""

from __future__ import annotations

import re

from crawler.sources.xianyu.extractor import (
    DETAIL_READY_JS,
    LIST_READY_JS,
    detail_ready_arg,
    list_ready_arg,
)

# 只取判据里对 opts 两个子对象的引用：sel.* → dom，signals.* → signals
_FIELD_RE = re.compile(r"\b(sel|signals)\.([A-Za-z_][A-Za-z0-9_]*)")


def _referenced_fields(js: str) -> set[tuple[str, str]]:
    return set(_FIELD_RE.findall(js))


def _assert_fields_provided(js: str, arg: dict[str, object]) -> None:
    referenced = _referenced_fields(js)
    assert referenced, "判据里没找到任何字段引用，正则或 JS 可能已变"

    for root, field in sorted(referenced):
        source = arg["dom"] if root == "sel" else arg["signals"]
        assert isinstance(source, dict)
        assert field in source, f"判据引用了 {root}.{field}，但 arg 里没有"


def test_list_ready_js_fields_are_provided() -> None:
    _assert_fields_provided(LIST_READY_JS, list_ready_arg())


def test_detail_ready_js_fields_are_provided() -> None:
    _assert_fields_provided(DETAIL_READY_JS, detail_ready_arg())


def test_list_ready_arg_shape() -> None:
    arg = list_ready_arg()
    dom = arg["dom"]
    signals = arg["signals"]

    assert isinstance(dom, dict)
    assert dom.get("card")
    # 判据必须能看到风控 / 登录 / 空结果三种信号，否则被拦时会白等满超时
    for key in ("requires_auth", "blocked", "empty"):
        assert isinstance(signals, dict)
        assert signals.get(key), key
    assert int(arg["timeout_ms"]) > 0  # type: ignore[call-overload]


def test_detail_ready_arg_shape() -> None:
    arg = detail_ready_arg()
    dom = arg["dom"]
    signals = arg["signals"]

    assert isinstance(dom, dict)
    for key in ("info", "price", "desc"):
        assert dom.get(key), key
    assert isinstance(signals, dict)
    assert signals.get("blocked")
    assert signals.get("requires_auth")
    # 超时取自 detail_dom.ready_timeout_ms，不是另写一个常量
    assert int(arg["timeout_ms"]) == int(dom.get("ready_timeout_ms") or 0)
