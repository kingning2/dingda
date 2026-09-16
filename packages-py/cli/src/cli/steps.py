"""Agent 步骤块：由后端决定 kind / page / status，前端只挂组件。

职责：
    把 toolCall / toolResult / browserFrame 收成 ``AgentWorkStepView`` 形状，
    供 SSE 下发；禁止前端再猜 preview → browser_crawl。
"""

from __future__ import annotations

import json
import re
import shlex
from typing import Any

_PLATFORM_LABEL = {
    "xianyu": "闲鱼",
    "xiaohongshu": "小红书",
    "ali1688": "1688",
}

# 会挂 PageCard / 收 browserFrame 的工具（含带前缀的变体，如 dingda_search）
_BROWSER_CRAWL_BASE = frozenset({"preview", "search", "product", "browse", "login"})

# 各 runtime 的「执行一条 shell」工具名。只对这些名字做命令还原 —— 文件类工具
# （read / write）的入参里也会出现路径与脚本文本，不能当命令解析。
_SHELL_TOOLS = frozenset(
    {
        "command_execution",
        "bash",
        "shell",
        "exec",
        "command",
        "terminal",
        "run",
    }
)

# 能从命令串里还原的业务工具；其余子命令（--help 等）一律放弃还原。
_BUSINESS_TOOLS = frozenset({"search", "product", "browse", "login", "preview", "compare"})
_BUSINESS_ALTERNATION = "|".join(sorted(_BUSINESS_TOOLS))

# 一次叮答工具调用在命令串里的入口标记，标记后的第一个词就是工具名：
#   tool search --platform xianyu --query "露营椅"
#   ".dingda-skills/dingda-crawl/scripts/run_tool.py" search --platform xianyu（旧入口）
# 裸 ``tool`` 太普通，必须紧跟已知子命令才算入口，否则任何提到 tool 的命令都会被误判。
_TOOL_ENTRY = re.compile(
    rf"(?:run_tool\.py|tools[./\\]cli(?:\.py)?"
    rf"|\btool(?:\.exe)?\b(?=\s+(?:{_BUSINESS_ALTERNATION})\b))"
)

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
    """去掉工具名前缀：``dingda_search`` / ``goofish_search`` → ``search``。"""
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


def _parse_cli_flags(tokens: list[str]) -> dict[str, Any]:
    """``--item-id x`` 序列 → ``{"item_id": "x"}``。无值的开关直接跳过。"""
    out: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            index += 1
            continue
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if following and not following.startswith("--"):
            out[token[2:].replace("-", "_")] = following
            index += 2
        else:
            index += 1
    return out


def _tokenize(tail: str) -> list[str]:
    """命令尾串 → tokens，容得下外层 shell 的包裹引号。

    实测（2026-09-15，codex 0.152 + Windows）：命令是

        "…\\powershell.exe" -Command 'tool search --platform xianyu --query "露营椅"'

    入口标记之后的那截是 ``search … --limit 20'`` —— 结尾那个孤立的 ``'`` 是外层
    ``-Command`` 的闭引号，POSIX 分词会直接抛 ``No closing quotation``。以前一抛
    就整个放弃还原，于是又退回「执行操作」。这里退化到 ``posix=False`` 分词
    （引号原样留在 token 里）再逐个剥掉，命令行仍能解出工具名与 ``--flag``。
    """
    try:
        return shlex.split(tail)
    except ValueError:
        pass
    try:
        return [token.strip("\"'") for token in shlex.split(tail, posix=False)]
    except ValueError:
        return []


def _shell_command(base_name: str, raw_input: Any) -> str:
    """shell 类工具的原始命令行；其余工具返回空串（它们没有可展示的命令）。"""
    if base_name.lower() not in _SHELL_TOOLS or not isinstance(raw_input, dict):
        return ""
    command = raw_input.get("command")
    return command.strip() if isinstance(command, str) else ""


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


def _recover_tool_call(base_name: str, raw_input: Any) -> tuple[str, dict[str, Any]] | None:
    """把一次 shell 命令还原成结构化工具调用；还原不了返回 None。

    skill 注入后业务工具不再以结构化 tool_call 下发，工具身份埋在命令串里，
    于是 label / 平台后缀 / PageCard 全部失效 —— 一律显示「执行操作」，右侧不挂页卡。
    这里把工具名与 ``--flag`` 解回来，重新走结构化那条分支。
    """
    command = _shell_command(base_name, raw_input)
    if not command:
        return None
    match = _TOOL_ENTRY.search(command)
    if match is None:
        return None
    # 旧入口标记通常紧跟一个闭引号（".dingda-skills/.../run_tool.py"），先剥掉再分词
    tail = command[match.end() :].lstrip("\"'")
    tokens = _tokenize(tail)
    if not tokens:
        return None
    tool = tokens[0].strip().lower()
    if tool not in _BUSINESS_TOOLS:
        return None
    if "--help" in tokens or "-h" in tokens:
        return None  # 查帮助不是真在取证，别冒充一次搜索
    return tool, _parse_cli_flags(tokens[1:])


# 工具名 → 面向用户的动作文案。
#
# 用户（尤其是毫无经验的人）只该看到「正在做什么」，不该看到 shell 命令、脚本路径
# 或原始 JSON —— 那些是实现细节。各 CLI 对同一件事的命名还不一样（codex 叫
# `command_execution`，opencode 叫 `bash`），所以统一在这里收口成中文动作。
_TOOL_LABELS = {
    # 业务工具
    "search": "搜索商品",
    "product": "查看商品详情",
    "browse": "连贯浏览",
    "login": "扫码登录",
    "preview": "预览网页",
    "compare": "比价找同款",
    # 技术工具：命令执行
    "command_execution": "执行操作",
    "bash": "执行操作",
    "shell": "执行操作",
    "exec": "执行操作",
    "command": "执行操作",
    "terminal": "执行操作",
    "run": "执行操作",
    # 技术工具：文件与检索
    "read": "读取资料",
    "write": "写入文件",
    "edit": "修改文件",
    "patch": "修改文件",
    "glob": "查找文件",
    "grep": "检索内容",
    "search_files": "检索内容",
    "list": "浏览目录",
    "ls": "浏览目录",
    "webfetch": "读取网页",
    "fetch": "读取网页",
    "websearch": "联网检索",
    "task": "调度子任务",
    "todowrite": "整理步骤",
    "todoread": "整理步骤",
}

# 这些工具的输入里只有命令 / 路径 / 文件内容，没有任何值得给用户看的东西，
# 因此一律不生成 hint（hint 会直接跟在步骤标题后面渲染）。
_OPAQUE_TOOLS = frozenset(
    {
        "read",
        "write",
        "edit",
        "patch",
        "glob",
        "grep",
        "search_files",
        "list",
        "ls",
        "webfetch",
        "fetch",
        "websearch",
        "task",
        "todowrite",
        "todoread",
    }
) | _SHELL_TOOLS


def _step_label(base_name: str, raw_input: Any) -> str:
    platform = ""
    if isinstance(raw_input, dict):
        platform = str(raw_input.get("platform") or "").strip().lower()
    label = _TOOL_LABELS.get(base_name.lower(), base_name)
    plat = _PLATFORM_LABEL.get(platform)
    if plat and base_name in {"search", "product", "login"}:
        return f"{label} · {plat}"
    return label


def _hint(value: Any) -> str | None:
    """从**结构化**结果里取一句给用户看的说明。

    只认 ``message`` / ``error_code``：它们是工具作者为「给人看」准备的字段。
    纯文本一律返回 None —— 那是原始 stdout / stderr / 文件内容，属于「执行了什么代码」，
    不是用户该看到的过程（2026-09-15 实测：命令报错原文与整份脚本内容曾被直接渲染到
    步骤标题后面）。
    """
    if not isinstance(value, dict):
        return None
    message = value.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()[:160]
    code = value.get("error_code")
    if isinstance(code, str) and code.strip():
        return code.strip()[:120]
    return None


def _step_hint(base_name: str, raw_input: Any) -> str | None:
    """步骤标题后的说明；技术工具一律不给（命令与路径不能给用户看）。"""
    if base_name.lower() in _OPAQUE_TOOLS:
        return None
    if isinstance(raw_input, dict):
        return _input_hint(base_name, raw_input)
    return _hint(raw_input)


def step_for_tool_call(call_id: str, name: str, raw_input: Any = None) -> dict[str, Any]:
    """toolCall → 完整 step（前端直接 upsert）。"""
    base = normalize_tool_name(name)
    command = _shell_command(base, raw_input)
    recovered = _recover_tool_call(base, raw_input)
    if recovered is not None:
        base, raw_input = recovered
    browser = _is_browser_crawl(base)
    step: dict[str, Any] = {
        "id": call_id,
        "label": _step_label(base, raw_input),
        "hint": _step_hint(base, raw_input),
        "kind": "browser_crawl" if browser else "tool",
        "status": dict(_STATUS_RUNNING),
    }
    if command:
        # label / hint 面向用户，command 只落进折叠区，供排查「到底跑了什么」
        step["command"] = command
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
    if base_name == "browse":
        query = str(raw_input.get("query") or "").strip()
        return f"浏览「{query}」" if query else "连贯浏览"
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
    patch: dict[str, Any] = {
        "id": call_id,
        "status": dict(_STATUS_DONE if effective_ok else _STATUS_ERROR),
        "hint": _hint(resolved),
        "page_loading": False,
    }
    text = _output_text(output)
    if text:
        # 不截断：商品提取依赖完整输出，折叠区也要能看到全文
        patch["output"] = text
    return patch


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
