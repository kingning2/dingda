"""外部 CLI 选品系统前言。

职责：
    把 ``system.md``、Skills、（换 Agent 时）叮答托管的先前对话与用户原文
    拼成一次 CLI stdin prompt。
    供 Codex / Claude / OpenCode spawn 使用。

设计说明：
    - 首轮 / 换 Agent 冷启动：系统前言 + Skill + 可选压缩历史 + 用户原文
    - 同 Agent 续聊（有 session）：只传 Skill 提醒 + 用户增量，记忆交给 CLI session
    - 历史与 Skill 注入块均经 Headroom 压缩（``DINGDA_HEADROOM=0`` 时透传）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_SYSTEM_PATH = Path(__file__).with_name("system.md")
_cached: str | None = None
_ROLE_LABELS = {"user": "用户", "assistant": "助手", "system": "系统"}


def system_prompt() -> str:
    """读选品系统前言（缓存）。"""
    global _cached
    if _cached is None:
        _cached = _SYSTEM_PATH.read_text(encoding="utf-8-sig").strip()
    return _cached


def format_prior_context(context_messages: list[dict[str, Any]] | None) -> str:
    """把叮答托管的先前对话压成可注入的 Markdown 区块；空则返回空串。"""
    if not context_messages:
        return ""
    cleaned: list[dict[str, Any]] = []
    for raw in context_messages:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "").strip()
        content = str(raw.get("content") or "").strip()
        if role not in _ROLE_LABELS or not content:
            continue
        cleaned.append({"role": role, "content": content})
    if not cleaned:
        return ""

    from src.agent.core.compress import compress_messages

    compressed = compress_messages(cleaned)
    lines = [
        "## 先前对话（叮答托管）",
        "",
        "以下为换 Agent 前由叮答托管的压缩上下文，请承接继续，勿重复已完成步骤。",
        "",
    ]
    for msg in compressed:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "user")
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"**{_ROLE_LABELS.get(role, role)}**：{content}")
        lines.append("")
    return "\n".join(lines).strip()


def compose_agent_prompt(
    user_prompt: str,
    *,
    platform_hint: str | None = None,
    resume: bool = False,
    workdir: Path | None = None,
    context_messages: list[dict[str, Any]] | None = None,
) -> str:
    """拼 stdin prompt；resume=True 时省略系统前言与叮答历史。"""
    text = (user_prompt or "").strip()
    skills = _skill_prompt(workdir)
    if resume:
        return f"{skills}\n---\n\n{text}\n" if text else skills

    parts = [system_prompt(), "", "---", "", skills, "", "---", ""]
    prior = format_prior_context(context_messages)
    if prior:
        parts += [prior, "", "---", ""]
    parts += ["## 用户请求", ""]
    hint = (platform_hint or "").strip().lower()
    if hint in {"xianyu", "xiaohongshu", "ali1688"}:
        label = {"xianyu": "闲鱼", "xiaohongshu": "小红书", "ali1688": "1688"}[hint]
        parts.append(
            f"本轮优先平台：{label}（platform=`{hint}`）。"
            "请按 `dingda-crawl` skill 里的命令调 `search` / `product` 取证，勿编造商品。"
            "闲鱼 / 小红书图文 search 会逐条拉详情；小红书优先读 content_text；视频暂跳过。"
        )
        parts.append("")
    parts.append(text)
    return "\n".join(parts).strip() + "\n"


def _skill_prompt(workdir: Path | None) -> str:
    """由宿主读取并注入爬虫 Skills，避免依赖各 CLI 的目录扫描行为。"""
    from src.cli.inject.mcp import server_dir
    from src.tools.skill import compose_skills_prompt

    python = (os.getenv("DINGDA_PYTHON") or "").strip() or str(Path(sys.executable).resolve())
    return compose_skills_prompt(server_dir(), python, cwd=workdir)
