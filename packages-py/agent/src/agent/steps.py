"""Agent 步骤块：由后端决定 kind / page / status，前端只挂组件。

职责：
    把一次工具调用收成 ``AgentWorkStepView`` 形状，随 ``toolCall`` / ``toolResult``
    下发；直播帧单独走 ``page_from_live_frame``（挂在同一个 step 的 ``page`` 上）。

设计说明：
    - ``hint`` 只认 ``message`` / ``error_code`` —— 它们是工具作者为「给人看」准备的字段。
      正文类字段（desc / comments）是给商品面板的，不该糊到步骤标题后面。
    - ``output`` 全文进「查看原始调用」折叠区，不截断：商品提取依赖完整输出。
    - 状态色号与前端 ``status-tone.ts`` 同源，改配色要两边一起改。
"""

from __future__ import annotations

import json
from typing import Any

_PLATFORM_LABEL = {
    "xianyu": "闲鱼",
    "xiaohongshu": "小红书",
    "ali1688": "1688",
}

# 与前端 status-tone.ts 的语义名对应：running / ready / error
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


def platform_label(platform: str) -> str:
    """平台 id → 中文名；未知平台原样返回（别把 id 藏起来，排查时要看得到）。"""
    key = (platform or "").strip().lower()
    return _PLATFORM_LABEL.get(key, key or "未知平台")


def step_label(template: str, platform: str) -> str:
    """把 label 模板里的 ``{platform}`` 换成中文平台名。"""
    if "{platform}" not in template:
        return template
    return template.replace("{platform}", platform_label(platform))


def step_for_call(
    call_id: str,
    *,
    label: str,
    hint: str | None,
    browser: bool,
    kind: str | None = None,
) -> dict[str, Any]:
    """开一次调用 → 完整 step（前端直接 upsert）。

    ``kind`` 覆盖默认推导：``browser`` → ``browser_crawl``，否则 ``tool``。
    扫码登录传 ``kind=\"login\"``，前端挂扫码块而不是浏览器直播页卡。
    """
    resolved = kind or ("browser_crawl" if browser else "tool")
    step: dict[str, Any] = {
        "id": call_id,
        "label": label,
        "hint": hint,
        "kind": resolved,
        "status": dict(_STATUS_RUNNING),
    }
    # login / browser_crawl 都要挂 page 壳：帧（二维码或截图）才有地方落
    if resolved in {"browser_crawl", "login"}:
        focus = hint or ("用 App 扫码登录" if resolved == "login" else "正在打开页面…")
        step["page"] = {
            "url": "",
            "title": label,
            "loading": True,
            "screenshot_url": None,
            "focus_label": focus,
        }
    return step


def step_for_result(call_id: str, output: Any = None) -> dict[str, Any]:
    """一次调用结束 → 状态补丁（前端按 id 合并进已有 step）。"""
    resolved = output if isinstance(output, dict) else None
    failed = isinstance(resolved, dict) and resolved.get("ok") is False
    patch: dict[str, Any] = {
        "id": call_id,
        "status": dict(_STATUS_ERROR if failed else _STATUS_DONE),
        "hint": result_hint(resolved),
        "page_loading": False,
    }
    text = _output_text(output)
    if text:
        patch["output"] = text
    return patch


def result_hint(output: Any) -> str | None:
    """从出参里取一句给用户看的说明；非 dict 或两个字段都没有则 None。"""
    if not isinstance(output, dict):
        return None
    message = output.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()[:160]
    code = output.get("error_code")
    if isinstance(code, str) and code.strip():
        return code.strip()[:120]
    return None


def page_from_live_frame(
    *,
    url: str,
    title: str,
    hint: str | None,
    screenshot_url: str,
) -> dict[str, Any]:
    """``browserFrame`` → ``page`` 字段（挂到进行中的 browser_crawl step）。"""
    return {
        "url": url,
        "title": title,
        "focus_label": hint,
        "loading": True,
        "screenshot_url": screenshot_url,
    }


def _output_text(output: Any) -> str:
    """原始输出文本：字符串原样，结构化结果转 JSON。仅用于折叠区展示。"""
    if isinstance(output, str):
        return output
    if output is None:
        return ""
    try:
        return json.dumps(output, ensure_ascii=False, default=str)
    except TypeError:
        return str(output)
