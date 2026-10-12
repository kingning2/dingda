"""DOM 选择器修复提议：内置 LLM 引擎。

职责：
    把 DomSnapshot 交给内置 LLM（OpenAI-compatible），从回复里抠出选择器补丁。

设计说明：
    - 引擎与 AgentService 同款环境变量：``DINGDA_LLM_BASE_URL`` / ``DINGDA_LLM_API_KEY``
      / ``DINGDA_LLM_MODEL``；可用 ``DINGDA_DOM_REPAIR_MODEL`` 单独覆盖修复模型
    - 验证一律回编排器（真跑一遍平台抽取脚本）；本层不出 shell、不起校验桥
    - JSON 提取容忍推理散文：括号配对 + 倒序 + 逐起点试探
    - 任何失败（无 key / 请求失败 / 无 JSON）都返回 None，由编排器按「本轮未成」继续
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterator

import httpx
from openai import AsyncOpenAI

from crawler.extraction.repair.types import DomPatch, DomSnapshot

logger = logging.getLogger("dingda.crawler.repair.propose")


def _llm_client() -> AsyncOpenAI:
    """与 agent 同款客户端装配；缺 key 直接报配置错误。"""
    api_key = os.getenv("DINGDA_LLM_API_KEY", "").strip()
    if not api_key:
        from core.errors import AppError

        raise AppError(
            "crawler.dom_repair_no_key",
            "未配置 DINGDA_LLM_API_KEY，AI 修选择器不可用",
            status_code=500,
        )
    base = os.getenv("DINGDA_LLM_BASE_URL", "").strip() or None
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base,
        timeout=_llm_timeout(),
        max_retries=1,
    )


def _llm_timeout() -> httpx.Timeout:
    """LLM 显式超时：SDK 默认 600s 修复链等不起（超时 → 抛错 → 上层返回 None 进下一轮）。

    connect 快失败（10s）、read 覆盖慢生成（默认 120s，``DINGDA_LLM_TIMEOUT`` 秒数可覆盖）。
    """
    seconds = float(os.getenv("DINGDA_LLM_TIMEOUT", "") or 120.0)
    return httpx.Timeout(connect=10.0, read=seconds, write=30.0, pool=10.0)


def _repair_model() -> str:
    """修复模型：``DINGDA_DOM_REPAIR_MODEL`` 优先，退回 ``DINGDA_LLM_MODEL``。"""
    model = (os.getenv("DINGDA_DOM_REPAIR_MODEL", "") or "").strip()
    if model:
        return model
    return (os.getenv("DINGDA_LLM_MODEL", "") or "").strip() or "gpt-4o"


def _system_prompt() -> str:
    return """你是电商页面 DOM 选择器修复助手。

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

禁止调用任何选品 / 搜索 / 商品工具。

【输出】
只输出一个 JSON 对象（不要 markdown、不要解释、不要多余键）。"""


def _user_prompt(snap: DomSnapshot) -> str:
    fields = [str(f) for f in snap.required_fields]
    lines = [
        _system_prompt(),
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
    lines.append(f"dom_tree={json.dumps(snap.tree, ensure_ascii=False)[:12000]}")
    lines.append(
        "只输出 JSON 对象：键只能用 current_selectors 里已有的字段名，"
        "其中 " + (", ".join(fields) if fields else "(无)") + " 必须全部给出。"
    )
    return "\n".join(lines)


def _iter_top_level_objects(text: str) -> Iterator[str]:
    """按花括号配对切出顶层 JSON 对象（跳过字符串内的花括号）。

    LLM 会把推理和答案混在一起输出；用括号配对比贪婪正则可靠：
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
    """从 LLM 输出里取 JSON 对象；答案通常在推理之后，故倒序尝试。"""
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
        logger.warning("repair llm json unparsable len=%s", len(blob))
    return best


async def propose_dom_patch(snap: DomSnapshot) -> DomPatch | None:
    """调内置 LLM 出补丁；失败返回 None（编排器按「本轮未成」继续）。"""
    prompt = _user_prompt(snap)
    logger.info(
        "repair llm start model=%s platform=%s section=%s",
        _repair_model(),
        snap.platform,
        snap.section,
    )
    try:
        client = _llm_client()
        resp = await client.chat.completions.create(
            model=_repair_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        joined = str(resp.choices[0].message.content or "")
    except Exception:
        # 契约：LLM 调用任何失败（网络 / key / 解析）都返回 None，编排器继续下一轮
        logger.warning("repair llm failed", exc_info=True)
        return None

    data = _extract_json(joined)
    if not data:
        logger.warning("repair llm no json len=%s", len(joined))
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
        logger.info("repair llm 丢弃非本 section 字段 %s", dropped[:10])
    if not selectors:
        return None
    merged = dict(snap.current_selectors)
    merged.update(selectors)
    return DomPatch(section=snap.section, selectors=merged, source="ai")
