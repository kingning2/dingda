"""Agent 步骤块：由后端决定 kind / page / status，前端只挂组件。

职责：
    把 toolCall / toolResult / browserFrame 收成 ``AgentWorkStepView`` 形状，
    供 SSE 下发；禁止前端再猜 preview → browser_crawl。
"""

from __future__ import annotations

import json
from typing import Any

_PLATFORM_LABEL = {
    "xianyu": "闲鱼",
    "xiaohongshu": "小红书",
    "ali1688": "1688",
}

# 会挂 PageCard / 收 browserFrame 的工具（含 MCP 前缀变体）
_BROWSER_CRAWL_BASE = frozenset({"preview", "search", "product", "login"})

_STATUS_RUNNING = {
    "state": "running",
    "label": "执行中",
    "hint": None,
    "badge_class": "bg-sky-500/15 text-sky-700",
}
_STATUS_DONE = {
    "state": "ready",
    "label": "已完成",
    "hint": None,
    "badge_class": "bg-emerald-500/15 text-emerald-600",
}
_STATUS_ERROR = {
    "state": "error",
    "label": "失败",
    "hint": None,
    "badge_class": "bg-red-500/15 text-red-700",
}


def normalize_tool_name(name: str) -> str:
    """去掉 MCP 服务器前缀：``dingda_search`` / ``goofish_search`` → ``search``。"""
    text = (name or "").strip()
    if not text:
        return "tool"
    for prefix in ("dingda_", "goofish_"):
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix) :]
    return text


def _is_browser_crawl(base_name: str) -> bool:
    return (
        base_name in _BROWSER_CRAWL_BASE
        or base_name.endswith("_search")
        or base_name.endswith("_product")
        or base_name.endswith("_preview")
        or base_name.endswith("_login")
    )


def _step_label(base_name: str, raw_input: Any) -> str:
    platform = ""
    if isinstance(raw_input, dict):
        platform = str(raw_input.get("platform") or "").strip().lower()
    plat = _PLATFORM_LABEL.get(platform)
    if plat and base_name in {"search", "product", "login"}:
        return f"{base_name} · {plat}"
    return base_name


def _hint(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:160]
        code = value.get("error_code")
        if isinstance(code, str) and code.strip():
            return code.strip()[:120]
    if isinstance(value, str):
        text = value.strip()
        return text[:160] if text else None
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        return None
    return text[:120] if text else None


def step_for_tool_call(call_id: str, name: str, raw_input: Any = None) -> dict[str, Any]:
    """toolCall → 完整 step（前端直接 upsert）。"""
    base = normalize_tool_name(name)
    browser = _is_browser_crawl(base)
    step: dict[str, Any] = {
        "id": call_id,
        "label": _step_label(base, raw_input),
        "hint": _hint(raw_input) if not isinstance(raw_input, dict) else _input_hint(base, raw_input),
        "kind": "browser_crawl" if browser else "tool",
        "status": dict(_STATUS_RUNNING),
    }
    if browser:
        url = ""
        if isinstance(raw_input, dict) and isinstance(raw_input.get("url"), str):
            url = raw_input["url"].strip()
        # search/product 一开始就挂 PageCard（loading），直播帧到了再填截图
        step["page"] = {
            "url": url,
            "title": step["label"],
            "loading": True,
            "screenshot_url": None,
            "focus_label": (
                _input_hint(base, raw_input)
                if isinstance(raw_input, dict)
                else "正在打开页面…"
            ),
        }
    return step


def _input_hint(base_name: str, raw_input: dict[str, Any]) -> str | None:
    if base_name == "search":
        query = str(raw_input.get("query") or "").strip()
        return f"搜索「{query}」" if query else "搜索"
    if base_name == "product":
        item_id = str(raw_input.get("item_id") or "").strip()
        return f"详情 {item_id}" if item_id else "拉详情"
    if base_name == "login":
        return "等待手机扫码"
    if base_name == "preview":
        url = str(raw_input.get("url") or "").strip()
        return url[:120] if url else "预览网页"
    return _hint(raw_input)


def step_for_tool_result(call_id: str, output: Any = None, *, ok: bool = True) -> dict[str, Any]:
    """toolResult → 状态补丁（合并进已有 step）。"""
    resolved = output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            resolved = parsed
    effective_ok = ok
    if isinstance(resolved, dict) and resolved.get("ok") is False:
        effective_ok = False
    return {
        "id": call_id,
        "status": dict(_STATUS_DONE if effective_ok else _STATUS_ERROR),
        "hint": _hint(resolved),
        "page_loading": False,
    }


def page_from_live_frame(
    *,
    url: str,
    title: str,
    hint: str | None,
    screenshot_url: str,
) -> dict[str, Any]:
    """browserFrame → page 字段（挂到进行中的 browser_crawl step）。"""
    return {
        "url": url,
        "title": title,
        "focus_label": hint,
        "loading": True,
        "screenshot_url": screenshot_url,
    }
