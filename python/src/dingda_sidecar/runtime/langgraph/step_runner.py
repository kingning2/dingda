"""比价图逐步编排器 — 节点门控 pause/cancel/seek/restart + 多模型。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from dingda_sidecar.agent.graph.config import GraphConfig
from dingda_sidecar.agent.graph.context import GraphContext
from dingda_sidecar.agent.graph.crawl_loop import needs_more_crawl
from dingda_sidecar.agent.graph.nodes.analyze import analyze_node
from dingda_sidecar.agent.graph.nodes.articles import article_analyze_node
from dingda_sidecar.agent.graph.nodes.finalize import finalize_node
from dingda_sidecar.agent.graph.nodes.keyword_refine import keyword_refine_node
from dingda_sidecar.agent.graph.nodes.match import match_node
from dingda_sidecar.agent.graph.nodes.normalize import normalize_node
from dingda_sidecar.agent.graph.nodes.planner import planner_node
from dingda_sidecar.agent.graph.nodes.search import crawl_node, web_research_node
from dingda_sidecar.agent.workflows.price_compare import PRICE_COMPARE_STEPS
from dingda_sidecar.config.settings import AiSettings
from dingda_sidecar.runtime.langgraph.errors import ErrorKind, GraphNodeError, classify_exception
from dingda_sidecar.runtime.langgraph.push import emit_run_progress
from dingda_sidecar.runtime.langgraph.run_control import (
    GraphRun,
    NodeModel,
    StepRecord,
    deep_copy_state,
    dumps_state,
)

logger = logging.getLogger("dingda.graph.step_runner")

AI_NODES = frozenset(
    {"web_research", "article_analyze", "planner", "analyze", "keyword_refine", "finalize"}
)


def _json_content(payload: dict[str, Any], *, limit: int = 12000) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)[:limit]
    except Exception:  # noqa: BLE001
        return str(payload.get("text") or "")[:limit]


def _item_preview(raw: dict[str, Any], *, platform: str) -> dict[str, str]:
    title = str(raw.get("title") or raw.get("item_title") or raw.get("name") or "").strip()
    url = str(raw.get("url") or raw.get("item_url") or raw.get("link") or "").strip()
    image = str(
        raw.get("image") or raw.get("pic_url") or raw.get("picUrl") or raw.get("img") or ""
    ).strip()
    if image.startswith("//"):
        image = f"https:{image}"
    price_obj = raw.get("price")
    if isinstance(price_obj, dict):
        price = str(price_obj.get("text") or price_obj.get("value") or "").strip()
    else:
        price = str(price_obj or raw.get("price_text") or "").strip()
    return {
        "platform": platform,
        "title": title[:160],
        "url": url,
        "image": image,
        "price": price[:40],
        "snippet": price[:40],
    }


def _step_content(node: str, state: dict[str, Any]) -> str:
    """把节点产物收成可给前端展示的文本 / JSON 信封。"""
    if node == "web_research":
        sources = state.get("web_sources") or []
        text = str(state.get("web_context") or "")
        if isinstance(sources, list) and sources:
            clean = []
            for item in sources[:24]:
                if not isinstance(item, dict):
                    continue
                clean.append(
                    {
                        "title": str(item.get("title") or "")[:160],
                        "url": str(item.get("url") or ""),
                        "snippet": str(item.get("snippet") or "")[:400],
                        "image": str(item.get("image") or ""),
                        "query": str(item.get("query") or ""),
                    }
                )
            return _json_content({"text": text[:2000], "sources": clean})
        return text[:4000]

    if node == "crawl":
        skipped = str(state.get("crawl_skipped") or "").strip()
        if skipped:
            return skipped
        items: list[dict[str, str]] = []
        for raw in (state.get("xianyu_items") or [])[:12]:
            if isinstance(raw, dict):
                items.append(_item_preview(raw, platform="闲鱼"))
        for raw in (state.get("alibaba_items") or [])[:12]:
            if isinstance(raw, dict):
                items.append(_item_preview(raw, platform="1688"))
        xy = len(state.get("xianyu_items") or [])
        ab = len(state.get("alibaba_items") or [])
        text = f"爬取完成：闲鱼 {xy} 条，1688 {ab} 条"
        if items:
            return _json_content({"text": text, "items": items})
        return text

    if node == "article_analyze":
        text = str(state.get("analysis") or "")
    elif node == "planner":
        plan = str(state.get("plan") or "").strip()
        keywords = state.get("keywords") or []
        kw_line = "、".join(str(item) for item in keywords if str(item).strip())
        if plan and kw_line:
            text = f"{plan}\n\n关键词：{kw_line}"
        else:
            text = plan or (f"关键词：{kw_line}" if kw_line else "")
    elif node == "normalize":
        text = f"字段归一：{len(state.get('normalized_items') or [])} 条"
    elif node == "match":
        text = f"同款配对：{len(state.get('matches') or [])} 组"
    elif node == "analyze":
        text = str(state.get("analysis") or "")
    elif node == "keyword_refine":
        keywords = state.get("keywords") or []
        kw_line = "、".join(str(item) for item in keywords if str(item).strip())
        round_num = int(state.get("crawl_round") or 0)
        if kw_line:
            text = f"第 {round_num} 轮补充关键词：{kw_line}"
        else:
            text = f"第 {round_num} 轮：数据已够，停止补充"
    elif node == "finalize":
        text = str(state.get("reply") or "")
    else:
        text = str(state.get("reply") or state.get("analysis") or "")
    return text[:4000]


def _crawl_sync(state: dict[str, Any], ctx: GraphContext) -> dict[str, Any]:
    import asyncio

    coro = crawl_node(state, ctx)  # type: ignore[arg-type]
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


NODE_FNS: dict[str, Callable[[dict[str, Any], GraphContext], dict[str, Any]]] = {
    "web_research": web_research_node,  # type: ignore[dict-item]
    "article_analyze": article_analyze_node,  # type: ignore[dict-item]
    "planner": planner_node,  # type: ignore[dict-item]
    "crawl": _crawl_sync,
    "normalize": normalize_node,  # type: ignore[dict-item]
    "match": match_node,  # type: ignore[dict-item]
    "analyze": analyze_node,  # type: ignore[dict-item]
    "finalize": finalize_node,  # type: ignore[dict-item]
}


def _push_llm_partial(
    run: GraphRun,
    *,
    node: str,
    index: int,
    text: str,
    account_id: str,
    model_name: str,
) -> None:
    clipped = text[:4000]
    with run.lock:
        rec: StepRecord | None = None
        for step in run.steps:
            if step.index == index:
                step.content = clipped
                step.status = "running"
                rec = step
                break
        if rec is None:
            rec = StepRecord(
                node=node,
                index=index,
                status="running",
                label=f"{index + 1}/{len(run.steps_order)} {node}",
                detail="生成中…",
                account_id=account_id,
                model=model_name,
                content=clipped,
            )
            run.steps.append(rec)
            run.steps.sort(key=lambda s: s.index)
    assert rec is not None
    emit_run_progress(run, rec)


def _ctx_for_node(
    run: GraphRun,
    node: str,
    index: int,
    account_id: str,
    model_name: str,
) -> GraphContext:
    model = run.node_models.get(node) or run.default_model
    if model is None:
        config = GraphConfig(system=run.system)
    else:
        settings = AiSettings(
            api_key=model.api_key,
            base_url=model.base_url,
            model_name=model.model,
            provider_type=model.provider_type or "openai",
            ai_enabled=True,
        )
        config = GraphConfig.from_ai_settings(settings, system=run.system)

    def on_llm(text: str) -> None:
        _push_llm_partial(
            run,
            node=node,
            index=index,
            text=text,
            account_id=account_id,
            model_name=model_name,
        )

    return GraphContext(config, steps=run.steps_order, on_llm=on_llm)


def _apply_pending(run: GraphRun) -> bool:
    """处理挂起的 restart/seek；返回是否应继续循环。"""
    with run.lock:
        action = run.pending_action
        seek_node = run.pending_seek_node
        override = run.pending_node_model
        run.pending_action = None
        run.pending_seek_node = None
        run.pending_node_model = None
        if override is not None and seek_node:
            run.node_models[seek_node] = override
        elif override is not None and 0 <= run.cursor < len(run.steps_order):
            # apply to current cursor node
            run.node_models[run.steps_order[run.cursor]] = override

    if action == "restart":
        with run.lock:
            run.state = deep_copy_state(run.initial_state)
            run.cursor = 0
            run.completed_nodes.clear()
            run.state_before.clear()
            run.reply = ""
            run.error = ""
            run.error_kind = ""
            run.failed_node = ""
            run.status = "running"
        return True

    if action == "seek" and seek_node:
        if seek_node not in run.steps_order:
            with run.lock:
                run.error = f"未知节点: {seek_node}"
                run.status = "failed"
            return False
        before = run.state_before.get(seek_node)
        if before is None and seek_node not in run.completed_nodes:
            # allow seek to current failed node using last state_before
            before = run.state_before.get(seek_node)
        if before is None:
            # if completed, we should have snapshot; else use initial when seeking entry
            if seek_node == run.steps_order[0]:
                before = deep_copy_state(run.initial_state)
            else:
                with run.lock:
                    run.error = f"节点尚未跑过，无法 seek: {seek_node}"
                    run.status = "failed"
                return False
        idx = run.steps_order.index(seek_node)
        with run.lock:
            run.state = deep_copy_state(before)
            run.cursor = idx
            run.completed_nodes = [n for n in run.completed_nodes if run.steps_order.index(n) < idx]
            # drop steps after seek
            run.steps = [s for s in run.steps if s.index < idx]
            run.reply = ""
            run.error = ""
            run.error_kind = ""
            run.failed_node = ""
            run.status = "running"
        return True

    return True


def _wait_if_paused(run: GraphRun) -> bool:
    """暂停等待；返回 False 表示已取消应退出。"""
    while True:
        if run.cancelled.is_set():
            with run.lock:
                run.status = "cancelled"
            emit_run_progress(run)
            return False
        if not run.paused.is_set():
            return True
        with run.lock:
            was_paused = run.status == "paused"
            run.status = "paused"
        if not was_paused:
            emit_run_progress(run)
        run.wake.wait(timeout=0.5)
        run.wake.clear()
        if run.pending_action in ("continue", "restart", "seek"):
            run.paused.clear()
            with run.lock:
                if run.status == "paused":
                    run.status = "running"
            return _apply_pending(run)


def _record_step(run: GraphRun, record: StepRecord) -> None:
    with run.lock:
        # replace same index if present
        run.steps = [
            s for s in run.steps if not (s.node == record.node and s.index == record.index)
        ]
        run.steps.append(record)
        run.steps.sort(key=lambda s: s.index)
    emit_run_progress(run, record)


def run_steps(run: GraphRun) -> None:
    """在后台线程执行线性 PRICE_COMPARE_STEPS。"""
    try:
        while True:
            if run.cancelled.is_set():
                with run.lock:
                    run.status = "cancelled"
                emit_run_progress(run)
                return

            # 先消费挂起的 restart/seek（失败后 respawn 也走这里）
            if run.pending_action and not _apply_pending(run):
                return

            if not _wait_if_paused(run):
                return

            if run.cursor >= len(run.steps_order):
                with run.lock:
                    run.reply = str(run.state.get("reply") or "")
                    run.status = "completed"
                emit_run_progress(run)
                return

            node = run.steps_order[run.cursor]
            index = run.cursor
            before = deep_copy_state(run.state)
            with run.lock:
                run.state_before[node] = before
                run.status = "running"

            model = run.node_models.get(node) or run.default_model
            account_id = model.account_id if model else ""
            model_name = model.model if model else ""

            _record_step(
                run,
                StepRecord(
                    node=node,
                    index=index,
                    status="running",
                    label=f"{index + 1}/{len(run.steps_order)} {node}",
                    detail="执行中…",
                    account_id=account_id,
                    model=model_name,
                    state_before_json=dumps_state(before),
                ),
            )
            logger.info(
                "agent_run.step.begin run_id=%s index=%s/%s node=%s model=%s account=%s",
                run.run_id,
                index + 1,
                len(run.steps_order),
                node,
                model_name or "-",
                account_id or "-",
            )

            ctx = _ctx_for_node(run, node, index, account_id, model_name)
            fn = NODE_FNS.get(node)
            if fn is None:
                with run.lock:
                    run.status = "failed"
                    run.error = f"未注册节点: {node}"
                    run.failed_node = node
                emit_run_progress(run)
                return

            # 短重试：network / rate_limit
            last_err: BaseException | None = None
            kind = ErrorKind.OTHER
            for attempt in range(3):
                if run.cancelled.is_set():
                    with run.lock:
                        run.status = "cancelled"
                    emit_run_progress(run)
                    return
                try:
                    if node in AI_NODES and model is None and not (run.default_model):
                        raise GraphNodeError(
                            f"节点 {node} 需要 AI 模型但未配置",
                            kind=ErrorKind.OTHER,
                        )
                    partial = fn(run.state, ctx)
                    if isinstance(partial, dict):
                        run.state.update(partial)
                    last_err = None
                    break
                except Exception as error:  # noqa: BLE001
                    last_err = error
                    kind = (
                        error.kind
                        if isinstance(error, GraphNodeError)
                        else classify_exception(error)
                    )
                    if kind == ErrorKind.BILLING:
                        break
                    if kind in (ErrorKind.NETWORK, ErrorKind.RATE_LIMIT) and attempt < 2:
                        time.sleep(0.4 * (attempt + 1))
                        continue
                    break

            if last_err is not None:
                msg = str(last_err)
                _record_step(
                    run,
                    StepRecord(
                        node=node,
                        index=index,
                        status="error",
                        label=f"{index + 1}/{len(run.steps_order)} {node}",
                        detail=msg[:500],
                        error_kind=kind.value,
                        account_id=account_id,
                        model=model_name,
                        state_before_json=dumps_state(before),
                    ),
                )
                with run.lock:
                    run.status = "waiting_network" if kind == ErrorKind.NETWORK else "failed"
                    run.error = msg[:500]
                    run.error_kind = kind.value
                    run.failed_node = node
                emit_run_progress(run)
                logger.warning(
                    "graph run failed run_id=%s node=%s kind=%s err=%s",
                    run.run_id,
                    node,
                    kind.value,
                    msg,
                )
                return

            content = _step_content(node, run.state)
            _record_step(
                run,
                StepRecord(
                    node=node,
                    index=index,
                    status="done",
                    label=f"{index + 1}/{len(run.steps_order)} {node}",
                    detail="完成",
                    account_id=account_id,
                    model=model_name,
                    state_before_json=dumps_state(before),
                    content=content,
                ),
            )
            sources = run.state.get("web_sources") if node == "web_research" else None
            source_urls = []
            if isinstance(sources, list):
                source_urls = [
                    str(item.get("url") or "")
                    for item in sources
                    if isinstance(item, dict) and item.get("url")
                ][:8]
            logger.info(
                "agent_run.step.done run_id=%s index=%s/%s node=%s "
                "content_chars=%s sources=%s preview=%s",
                run.run_id,
                index + 1,
                len(run.steps_order),
                node,
                len(content or ""),
                source_urls or "-",
                (content or "")[:180].replace("\n", " "),
            )

            next_cursor = index + 1
            if node == "analyze" and needs_more_crawl(run.state):
                refine_ctx = _ctx_for_node(
                    run,
                    "keyword_refine",
                    index,
                    account_id,
                    model_name,
                )
                partial_refine = keyword_refine_node(run.state, refine_ctx)  # type: ignore[arg-type]
                if isinstance(partial_refine, dict):
                    run.state.update(partial_refine)
                refine_content = _step_content("keyword_refine", run.state)
                _record_step(
                    run,
                    StepRecord(
                        node="keyword_refine",
                        index=index,
                        status="done",
                        label=f"补充关键词（第 {int(run.state.get('crawl_round') or 0)} 轮）",
                        detail="完成",
                        account_id=account_id,
                        model=model_name,
                        content=refine_content,
                    ),
                )
                if run.state.get("continue_crawl"):
                    next_cursor = PRICE_COMPARE_STEPS.index("crawl")
                    logger.info(
                        "agent_run.crawl_loop run_id=%s round=%s next=crawl keywords=%s",
                        run.run_id,
                        run.state.get("crawl_round"),
                        run.state.get("keywords"),
                    )

            with run.lock:
                if node not in run.completed_nodes:
                    run.completed_nodes.append(node)
                run.cursor = next_cursor

    except Exception as error:  # noqa: BLE001
        logger.exception("step runner crashed run_id=%s", run.run_id)
        with run.lock:
            run.status = "failed"
            run.error = str(error)[:500]
            run.error_kind = ErrorKind.OTHER.value
        emit_run_progress(run)


def build_initial_state(user: str) -> dict[str, Any]:
    return {
        "query": user,
        "plan": "",
        "keywords": [],
        "keywords_used": [],
        "crawl_round": 0,
        "continue_crawl": True,
        "web_context": "",
        "web_sources": [],
        "knowledge_context": "",
        "xianyu_items": [],
        "alibaba_items": [],
        "normalized_items": [],
        "matches": [],
        "analysis": "",
        "reply": "",
    }


def make_default_model(
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> NodeModel | None:
    if not (base_url and api_key and model):
        return None
    return NodeModel(
        node="*",
        base_url=base_url,
        api_key=api_key,
        model=model,
    )


# re-export for handlers
__all__ = [
    "AI_NODES",
    "PRICE_COMPARE_STEPS",
    "build_initial_state",
    "make_default_model",
    "run_steps",
]
