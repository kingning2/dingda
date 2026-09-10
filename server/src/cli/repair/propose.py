"""外部 CLI：DOM 选择器修复（子 agent 角色）。

职责：
    把 DomSnapshot 发给 Codex/Claude/OpenCode，解析 stdout 中的 JSON 补丁。

设计说明：
    - 走 ``run_cli(..., role="child")``：不拼 system.md / 平台提示，cwd 隔离
    - 给了 ``validate_url`` 就让它**自验**：prompt 里给出
      ``python -m src.tools.validate_cli`` 这条命令（回打修复现场那一页）；
      也顺带注入 MCP 的 ``validate_selectors``，哪个能用用哪个
    - 没给 ``validate_url`` 就退回「出选择器，等编排器验」
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Iterator

from src.cli.spawn import run_cli
from src.crawler.extraction.repair.types import DomPatch, DomSnapshot

logger = logging.getLogger("dingda.cli.repair.propose")


def _system_prompt(*, can_validate: bool = False) -> str:
    text = """你是电商页面 DOM 选择器修复助手。

【选择器怎么被使用】
每个字段的选择器会被单独执行 document.querySelector(sel)，取第一个命中的元素，
再读它的文本（img 则读 src）当作该字段的值。所以它必须「命中唯一一个真正代表该
字段的元素」——多套住一层容器，就会把兄弟节点的文案一起抓进来。

【页面特征】
站点用 CSS Modules，class 名带哈希（如 price--OEWLbcxC）。哈希会变，所以不要用
完整 class 名，一律用 [class*="语义片段"]（片段取哈希前那截）。

【dom_tree 怎么读】
- classes：完整 class 名（含哈希），片段从这里截。
- text：该节点自身的直接文本，子节点的文本不一定包含在内。
- kids：子节点；深度 / 数量有截断，kids 为空不代表内部没有元素，可能只是没展开。

【规则】
1. 只从 dom_tree 出现过的 class 片段取材，不要凭空编造类名。
2. 优先选「最深的、自身文本就是该字段值」的元素，不要选外层容器。
3. 能用一个稳定祖先限定范围就限定，如 [class*="item-main-info"] [class*="price"]；
   避免裸 [class*="x"] 误命中页面其它区域（推荐位、页头）。
4. 按字段名判断该选什么：img → <img> 本身；count/want/browse → 数字文本；
   nick/name/author/title → 承载该名字的元素；card/container/info/main → 这类才是容器。
5. 给了 last_attempt_* 时：把它和该字段应有的值对比，判断上一轮是「套了外层容器」、
   「混进噪音」还是「没命中」，据此修正，不要重复同一个选择器。
6. 输出前自检：这个选择器会不会命中多个元素？会不会套住容器？拿不准就再收敛一点。
7. 只写**标准 CSS**：属性 / 后代 / 子代 / `:first-child` / `:nth-child(n)` 都可以；
   不要用 `:has-text(...)`、`:contains(...)`、`:visible` 这类 Playwright / jQuery 伪类 ——
   它们对 `document.querySelector` 是**非法选择器**，会直接报错。

【输出】
只输出一个 JSON 对象（不要 markdown、不要解释、不要多余键）。"""
    if can_validate:
        text += f"""

【自验】
出完选择器**先跑这条命令**（在 shell 里执行，别找 MCP 工具）：
    "{sys.executable}" -m src.tools.validate_cli --selectors '<JSON>'
把 <JSON> 换成一个 JSON 对象（字段名 → 选择器）；也可以先写进文件再用 @路径 传。
它会在**正在修的那个页面**上真实跑一遍，把平台抽取脚本的输出打回来：
字段有值就对了；返回 error、字段为空、或串进别的文案，就据此改，改到抽对为止。
最后只输出 JSON 对象（不要 markdown、不要解释、不要多余键）。"""
    else:
        text += """

禁止调用任何选品 / 搜索 / 商品工具。"""
    return text


def _catalog_default_agent() -> str:
    """catalog 里被标为默认的 runtime id（用户在应用里装/选的）。"""
    from src.infrastructure.db import settings as settings_repo

    try:
        rows = settings_repo.get_agent_runtimes_catalog()
    except Exception:  # noqa: BLE001
        logger.debug("读 agent catalog 失败", exc_info=True)
        return ""
    for row in rows:
        if isinstance(row, dict) and row.get("is_default"):
            return str(row.get("id") or "").strip()
    return ""


def _repair_runtime() -> tuple[str, str | None]:
    """修复子 agent 用哪个 runtime / 哪个模型 —— **跟着用户的选择走**。

    优先级：

    1. ``DINGDA_DOM_REPAIR_RUNTIME`` 环境变量（运维/测试强制指定）
    2. 应用设置 ``default_agent_id``（用户在界面上选的 agent）
    3. catalog 里 ``is_default`` 的 runtime
    4. 注册表里第一个

    模型取用户为该 agent 选的 ``default_models[agent]``；没选就不传，交给 CLI 自己的默认
    （opencode 没模型会直接报错，所以有就一定要带上）。
    """
    from src.cli.registry import list_runtime_ids
    from src.infrastructure.db import settings as settings_repo

    runtime = (os.getenv("DINGDA_DOM_REPAIR_RUNTIME") or "").strip()
    model: str | None = None
    try:
        if not runtime:
            runtime = (settings_repo.get_default_agent_id() or "").strip()
        if runtime:
            model = (settings_repo.get_default_models().get(runtime) or "").strip() or None
    except Exception:  # noqa: BLE001 - 设置读不到不该拖垮修复
        logger.debug("读用户默认 agent/model 失败", exc_info=True)
    if not runtime:
        runtime = _catalog_default_agent()
    if not runtime:
        runtime = (list_runtime_ids() or [""])[0]
    return runtime, model


def _runtime_id() -> str:
    return _repair_runtime()[0]


def _compress_tree(tree: dict[str, Any]) -> dict[str, Any]:
    """进 prompt 前用该 runtime 的 ``compress_payload`` 压一轮。

    取不到插头 / 压缩出错都透传：压缩是省 token，不能让修复挂掉。
    """
    try:
        from src.cli.registry import get_runtime

        return get_runtime(_runtime_id()).compress_payload(tree, label="dom_tree")
    except Exception:  # noqa: BLE001
        logger.debug("dom_tree compress skipped", exc_info=True)
        return tree


def _user_prompt(snap: DomSnapshot, *, can_validate: bool = False) -> str:
    fields = [str(f) for f in snap.required_fields]
    lines = [
        _system_prompt(can_validate=can_validate),
        "",
        f"platform={snap.platform}",
        f"section={snap.section}",
        f"item_id={snap.item_id}",
        f"url={snap.url}",
        f"required_fields={json.dumps(fields, ensure_ascii=False)}",
        f"current_selectors={json.dumps(snap.current_selectors, ensure_ascii=False)}",
    ]
    if snap.last_error or snap.last_payload is not None:
        lines.append(f"last_attempt_error={snap.last_error or ''}")
        lines.append(
            "last_attempt_payload="
            + json.dumps(snap.last_payload or {}, ensure_ascii=False)[:1500]
        )
    lines.append(f"dom_tree={json.dumps(_compress_tree(snap.tree), ensure_ascii=False)[:12000]}")
    lines.append(
        "只输出 JSON 对象：键只能用 current_selectors 里已有的字段名，"
        "其中 " + (", ".join(fields) if fields else "(无)") + " 必须全部给出。"
    )
    return "\n".join(lines)


def _iter_top_level_objects(text: str) -> Iterator[str]:
    """按花括号配对切出顶层 JSON 对象（跳过字符串内的花括号）。

    CLI 会把推理和答案混在一起流式吐出；用括号配对比贪婪正则可靠：
    贪婪 ``\\{[\\s\\S]*\\}`` 会从推理里第一个 ``{`` 一路吃到答案的最后一个
    ``}``，中间夹着散文就无法解析。
    """
    depth = 0
    start = -1
    in_str = False
    escaped = False
    for index, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = index
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start : index + 1]


def _match_object(text: str, start: int) -> str | None:
    """从 ``start`` 处的 ``{`` 找配对 ``}``（跳过字符串），返回子串或 None。"""
    depth = 0
    in_str = False
    escaped = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _extract_json(text: str) -> dict[str, Any] | None:
    """从 CLI 输出里取 JSON 对象；答案通常在推理之后，故倒序尝试。"""
    blob = (text or "").strip()
    if not blob:
        return None
    try:
        whole = json.loads(blob)
        if isinstance(whole, dict):
            return whole
    except json.JSONDecodeError:
        pass
    for block in reversed(list(_iter_top_level_objects(blob))):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    # 推理里若有落单的 ``{``，配对会被带偏；退化为逐起点试探，取最长的可解析块。
    best: dict[str, Any] | None = None
    best_len = 0
    for start, ch in enumerate(blob):
        if ch != "{":
            continue
        block = _match_object(blob, start)
        if block is None or len(block) <= best_len:
            continue
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            best, best_len = data, len(block)
    if best is None:
        logger.warning("repair cli json unparsable len=%s", len(blob))
    return best


async def propose_dom_patch(
    snap: DomSnapshot,
    *,
    validate_url: str | None = None,
) -> DomPatch | None:
    """调用外部 CLI，返回 DomPatch；失败返回 None。

    给了 ``validate_url`` 就把子 agent 的 MCP 指到修复现场：
    它能自己调 ``validate_selectors`` 试跑，不必等下一轮。
    """
    runtime, model_id = _repair_runtime()
    prompt = _user_prompt(snap, can_validate=bool(validate_url))
    logger.info(
        "repair cli start runtime=%s model=%s platform=%s section=%s",
        runtime,
        model_id or "(默认)",
        snap.platform,
        snap.section,
    )
    chunks: list[str] = []
    try:
        async for event in run_cli(
            runtime,
            prompt,
            role="child",
            model_id=model_id,
            mcp_env={"DINGDA_VALIDATE_URL": validate_url} if validate_url else None,
        ):
            kind = str(event.get("type") or "")
            if kind in {"textDelta", "thinking"}:
                text = event.get("text")
                if isinstance(text, str) and text:
                    chunks.append(text)
            if kind == "error":
                logger.warning("repair cli error %s", event.get("message"))
                return None
    except Exception:  # noqa: BLE001
        logger.exception("repair cli failed")
        return None

    joined = "".join(chunks)
    data = _extract_json(joined)
    if not data:
        logger.warning("repair cli no json len=%s", len(joined))
        return None
    # 只收 str 值、且必须是本 section 已有的字段名；
    # 否则 AI 顺手多吐一个键（如 "analysis"）就会永久写进 extract.json
    known = {str(k) for k in snap.current_selectors}
    selectors = {
        str(k): str(v)
        for k, v in data.items()
        if isinstance(k, str) and isinstance(v, str) and v.strip() and k in known
    }
    dropped = sorted(str(k) for k in data if str(k) not in known)
    if dropped:
        logger.info("repair cli 丢弃非本 section 字段 %s", dropped[:10])
    if not selectors:
        return None
    merged = dict(snap.current_selectors)
    merged.update(selectors)
    return DomPatch(section=snap.section, selectors=merged, source="ai")
