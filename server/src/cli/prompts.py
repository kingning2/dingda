"""外部 CLI 选品系统前言。

职责：
    把 ``system.md`` 与用户原文拼成一次 CLI stdin prompt。
    供 Codex / Claude / OpenCode spawn 使用；续聊（有 session）只传用户增量。

设计说明：
    - 首轮：系统前言 + 可选平台提示 + 用户原文
    - 续聊：只传用户原文，记忆交给 CLI session
"""

from __future__ import annotations

from pathlib import Path

_SYSTEM_PATH = Path(__file__).with_name("system.md")
_cached: str | None = None


def system_prompt() -> str:
    """读选品系统前言（缓存）。"""
    global _cached
    if _cached is None:
        _cached = _SYSTEM_PATH.read_text(encoding="utf-8-sig").strip()
    return _cached


def compose_agent_prompt(
    user_prompt: str,
    *,
    platform_hint: str | None = None,
    resume: bool = False,
) -> str:
    """拼 stdin prompt；resume=True 时省略系统前言。"""
    text = (user_prompt or "").strip()
    if resume:
        return f"{text}\n" if text else "\n"

    parts = [system_prompt(), "", "---", "", "## 用户请求", ""]
    hint = (platform_hint or "").strip().lower()
    if hint in {"xianyu", "xiaohongshu", "ali1688"}:
        label = {"xianyu": "闲鱼", "xiaohongshu": "小红书", "ali1688": "1688"}[hint]
        parts.append(
            f"本轮优先平台：{label}（platform=`{hint}`）。"
            "请用 MCP 工具 `search` / `product` 取证，勿编造商品。"
            "闲鱼 / 小红书图文 search 会逐条拉详情；小红书优先读 content_text；视频暂跳过。"
        )
        parts.append("")
    parts.append(text)
    return "\n".join(parts).strip() + "\n"
