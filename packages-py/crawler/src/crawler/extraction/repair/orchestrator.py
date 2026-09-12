"""DOM 修复编排：指纹 → AI CLI → 验证 → 写回。

职责：
    在确认非风控/非登录墙后，尝试修复 detail_dom（或其它 section），
    验证通过则 persist 并返回可用来组 CrawlItem 的 payload。
"""

from __future__ import annotations

import logging
from typing import Any

from contracts.browser_port import Page
from crawler.extraction.fingerprint import (
    best_node_for_selector,
    nodes_from_tree,
    relocate_section,
    save_fingerprint,
)
from crawler.extraction.repair import gates
from crawler.extraction.repair.bridge import ValidationBridge
from crawler.extraction.repair.dump import dump_dom_tree
from crawler.extraction.repair.persist import persist_patch
from crawler.extraction.repair.types import (
    DomPatch,
    DomSnapshot,
    PlatformRepairAdapter,
    RepairResult,
)
from core.errors import AppError

logger = logging.getLogger("dingda.crawler.repair.orchestrator")


async def repair_detail_dom(
    page: Page,
    adapter: PlatformRepairAdapter,
    *,
    item_id: str,
) -> RepairResult:
    """指纹 + AI 循环修复；成功返回 payload。"""
    if not gates.repair_enabled():
        return RepairResult(ok=False, error="crawler.dom_repair_disabled")

    platform = adapter.platform
    if not gates.try_acquire_platform(platform):
        return RepairResult(ok=False, error="crawler.dom_repair_busy")

    bridge: ValidationBridge | None = None
    try:
        roots = adapter.dump_roots()
        tree = await dump_dom_tree(page, roots=roots)
        preview = str(tree.get("preview") or "")
        if gates.looks_risk_text(preview):
            return RepairResult(ok=False, error="channel.risk")

        base = adapter.current_selectors()
        # 上一轮失败的现场：逐轮累积，下一轮跟选择器一起喂给 CLI，避免盲改
        last_payload: dict[str, Any] | None = None
        last_reason: str | None = None
        fields = [f for f in adapter.required_fields() if f in base]
        relocated = relocate_section(
            platform,
            adapter.section_name,
            fields,
            tree,
            base,
        )
        if relocated:
            payload = await _evaluate(adapter, page, relocated, item_id)
            if adapter.is_risk_payload(payload):
                return RepairResult(ok=False, error="channel.risk")
            if adapter.is_auth_payload(payload):
                return RepairResult(ok=False, error="account.session_expired")
            if adapter.payload_ok(payload):
                patch = DomPatch(
                    section=adapter.section_name,
                    selectors=relocated,
                    source="fingerprint",
                )
                persist_patch(adapter.extract_beside, patch)
                _save_fps_from_tree(platform, adapter.section_name, fields, relocated, tree)
                return RepairResult(ok=True, payload=payload, patch=patch)
            # 指纹重定位也没抽对：把现场留给 AI 轮
            last_payload = payload
            last_reason = str(payload.get("error") or "payload-not-ok")

        # AI 轮之前起校验桥：子 agent 能自己回打「正在修的这一页」试跑选择器，
        # 不必等下一轮才知道对不对
        bridge = ValidationBridge(page, adapter, item_id=item_id)
        validate_url = bridge.start()

        rounds = gates.max_rounds()
        last_err = "dom_repair_failed"
        for round_i in range(1, rounds + 1):
            if not gates.consume_ai_budget():
                last_err = "crawler.dom_repair_budget"
                break
            snap = DomSnapshot(
                platform=platform,
                section=adapter.section_name,
                url=str(tree.get("url") or getattr(page, "url", "") or ""),
                item_id=item_id,
                current_selectors=base,
                tree=tree,
                required_fields=adapter.required_fields(),
                last_error=last_reason,
                last_payload=last_payload,
            )
            logger.info(
                "repair ai round=%s/%s platform=%s item_id=%s",
                round_i,
                rounds,
                platform,
                item_id,
            )
            from cli.repair.propose import propose_dom_patch

            patch = await propose_dom_patch(snap, validate_url=validate_url)
            if patch is None:
                last_err = "crawler.dom_repair_failed"
                last_reason = "cli-no-json：CLI 没吐出可解析的 JSON 补丁"
                continue
            # 再 dump 一次防中途变风控页
            tree = await dump_dom_tree(page, roots=roots)
            if gates.looks_risk_text(str(tree.get("preview") or "")):
                return RepairResult(ok=False, error="channel.risk")
            payload = await _evaluate(adapter, page, patch.selectors, item_id)
            if adapter.is_risk_payload(payload):
                return RepairResult(ok=False, error="channel.risk")
            if adapter.is_auth_payload(payload):
                return RepairResult(ok=False, error="account.session_expired")
            if not adapter.payload_ok(payload):
                last_err = "crawler.dom_repair_failed"
                base = patch.selectors
                last_payload = payload
                last_reason = str(payload.get("error") or "payload-not-ok")
                continue
            persist_patch(adapter.extract_beside, patch)
            _save_fps_from_tree(platform, adapter.section_name, fields, patch.selectors, tree)
            return RepairResult(ok=True, payload=payload, patch=patch)

        return RepairResult(ok=False, error=last_err)
    finally:
        if bridge is not None:
            bridge.stop()
        gates.release_platform(platform)


async def _evaluate(
    adapter: PlatformRepairAdapter,
    page: Page,
    selectors: dict[str, Any],
    item_id: str,
) -> dict[str, Any]:
    """跑平台抽取脚本。

    选择器非法（模型爱写 ``:has-text(...)`` 这类非 CSS 伪类）会让 ``querySelector``
    抛异常 —— 按「这次没抽到」处理，别把整条抓取带崩。
    """
    try:
        payload = await adapter.evaluate_extract(page, selectors, item_id=item_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("repair evaluate failed: %s", exc)
        return {"error": "selector-invalid", "message": str(exc)[:200]}
    return payload if isinstance(payload, dict) else {"error": "dom-empty"}


def _save_fps_from_tree(
    platform: str,
    section: str,
    fields: list[str],
    selectors: dict[str, Any],
    tree: dict[str, Any],
) -> None:
    """按字段选择器在树里定位对应节点，存其指纹供下次 relocate。"""
    nodes = nodes_from_tree(tree)
    if not nodes:
        return
    for field in fields:
        selector = selectors.get(field)
        if not isinstance(selector, str) or not selector.strip():
            continue
        node = best_node_for_selector(nodes, selector)
        if node is None:
            continue
        try:
            save_fingerprint(platform, section, field, node)
        except Exception:  # noqa: BLE001
            logger.debug("save fingerprint skipped field=%s", field, exc_info=True)
            continue
        # 已存字段指纹；其余字段继续收集


def raise_repair_error(result: RepairResult) -> None:
    """把失败 RepairResult 映射为 AppError。"""
    code = result.error or "crawler.dom_repair_failed"
    if code == "channel.risk":
        raise AppError("channel.risk", "DOM 修复时仍处于风控页", status_code=403)
    if code == "account.session_expired":
        raise AppError(
            "account.session_expired",
            "DOM 修复时遇到登录墙",
            status_code=401,
        )
    raise AppError(code, f"详情 DOM 自动修复失败：{code}", status_code=502)
