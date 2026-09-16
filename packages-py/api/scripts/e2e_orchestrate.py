"""CLI 主编排器端到端验收。

职责：
    不启真实外部 LLM / 不启 Tauri：把「父派工 → worker 报 needs_repair →
    repair_dom → child_resume」整条握手跑通，并核对 Store 阶段与 live agentPhase。

设计说明：
    - ``run_cli`` 用假事件流替代真实 Codex/Claude
    - ``repair_dom`` 里的 ``run_product`` 用假成功结果替代真爬虫
      （patch ``tools.product.run_product``，因 repair_dom 是函数内 import）
    - 角色面 / Skill 面 / RepairOwner / 工具注册用真实现

使用示例：
    uv run --directory packages-py/api python scripts/e2e_orchestrate.py
    pnpm --filter @v2/e2e e2e:orchestrate
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("dingda.e2e.orchestrate")


@dataclass
class CheckResult:
    """单项结果。"""

    name: str
    ok: bool
    details: dict[str, Any]


def _check_role_surfaces() -> CheckResult:
    """父只编排、worker 只取证、child 无人设。"""
    from cli.roles import ChildRole, ParentRole, WorkerRole, list_role_ids
    from cli.skill import ORCHESTRATE_SKILL_NAMES, WORKER_SKILL_NAMES

    os.environ["DINGDA_HEADROOM"] = "0"
    parent = ParentRole()
    worker = WorkerRole()
    child = ChildRole()
    parent_text = parent.compose_prompt("帮我找露营椅")
    worker_text = worker.compose_prompt("搜闲鱼露营椅", platform_hint="xianyu")
    child_text = child.compose_prompt("只修这一页")
    ok = (
        set(list_role_ids()) == {"parent", "worker", "child"}
        and parent.skill_ids() == ORCHESTRATE_SKILL_NAMES
        and worker.skill_ids() == WORKER_SKILL_NAMES
        and child.skill_ids() == ()
        and child.uses_system_prompt is False
        and "child_run" in parent_text
        and "dingda-crawl" not in parent_text
        and "dingda-crawl" in worker_text
        and "crawler.needs_repair" in worker_text
        and worker.session_env().get("DINGDA_REPAIR_OWNER") == "parent"
        and child_text.strip() == "只修这一页"
    )
    return CheckResult(
        name="role-surfaces",
        ok=ok,
        details={
            "roles": list_role_ids(),
            "parent_skills": list(parent.skill_ids()),
            "worker_skills": list(worker.skill_ids()),
            "parent_has_child_run": "child_run" in parent_text,
            "worker_has_crawl": "dingda-crawl" in worker_text,
            "worker_repair_owner": worker.session_env().get("DINGDA_REPAIR_OWNER"),
            "child_bare": child_text.strip() == "只修这一页",
        },
    )


def _check_tool_registry() -> CheckResult:
    """编排五工具已注册进 registry，且不标 internal_only。"""
    from tools.registry import get_tool, list_tools

    names = {spec.name for spec in list_tools()}
    needed = {
        "child_run",
        "child_resume",
        "child_cancel",
        "child_status",
        "repair_dom",
    }
    missing = sorted(needed - names)
    public = []
    for name in sorted(needed):
        if name not in names:
            continue
        spec = get_tool(name)
        public.append({"name": name, "internal_only": spec.internal_only})
    ok = not missing and all(not row["internal_only"] for row in public)
    return CheckResult(
        name="tool-registry",
        ok=ok,
        details={"missing": missing, "specs": public},
    )


def _check_repair_owner() -> CheckResult:
    """默认上抛 needs_repair；crawler 才内联。"""
    from crawler.extraction.repair.owner import (
        EscalateToParent,
        InlineCrawlerRepair,
        get_repair_owner,
    )

    os.environ.pop("DINGDA_REPAIR_OWNER", None)
    default_ok = isinstance(get_repair_owner(), EscalateToParent)
    os.environ["DINGDA_REPAIR_OWNER"] = "crawler"
    inline_ok = isinstance(get_repair_owner(), InlineCrawlerRepair)
    os.environ["DINGDA_REPAIR_OWNER"] = "parent"
    parent_ok = isinstance(get_repair_owner(), EscalateToParent)
    return CheckResult(
        name="repair-owner",
        ok=default_ok and inline_ok and parent_ok,
        details={
            "default_escalate": default_ok,
            "crawler_inline": inline_ok,
            "parent_escalate": parent_ok,
        },
    )


async def _fake_worker_run_cli(*_args: Any, **_kwargs: Any):
    """假 worker：跑 search → 报 needs_repair → 结束。"""
    yield {"type": "runStarted", "runtimeId": "codex", "runId": "ignored"}
    yield {"type": "session", "sessionId": "ses_worker_e2e"}
    yield {
        "type": "toolCall",
        "id": "call_1",
        "name": "search",
        "input": {"platform": "xianyu", "query": "露营椅"},
    }
    yield {
        "type": "toolResult",
        "id": "call_1",
        "output": json.dumps(
            {
                "ok": False,
                "error_code": "crawler.needs_repair",
                "message": "DOM 失效",
                "repair": {
                    "platform": "xianyu",
                    "item_id": "731",
                    "url": "https://www.goofish.com/item?id=731",
                },
            },
            ensure_ascii=False,
        ),
    }
    yield {
        "type": "textDelta",
        "text": "爬虫 DOM 失效，已上报父进程修复 error_code=crawler.needs_repair",
    }
    yield {"type": "runCompleted", "exitCode": 1}


async def _fake_resume_run_cli(*_args: Any, **_kwargs: Any):
    """假续聊：修复后正常完成。"""
    yield {"type": "runStarted", "runtimeId": "codex", "runId": "ignored"}
    yield {"type": "session", "sessionId": "ses_worker_e2e"}
    yield {"type": "textDelta", "text": "修复完成，继续取证，已拿到 3 条商品。"}
    yield {"type": "runCompleted", "exitCode": 0}


async def _fake_cancel_run_cli(*_args: Any, **_kwargs: Any):
    """假长跑：先 running，等 cancel。"""
    yield {"type": "runStarted", "runtimeId": "codex", "runId": "ignored"}
    yield {"type": "session", "sessionId": "ses_cancel"}
    yield {"type": "toolCall", "id": "c1", "name": "search", "input": {"query": "x"}}
    await asyncio.sleep(0.05)
    yield {"type": "runCompleted", "exitCode": 0}


async def _check_handshake() -> CheckResult:
    """child_run → needs_repair → repair_dom → child_resume。"""
    from cli import live as live_hub
    from cli.lifecycle import AgentPhase
    from cli.registry import get_run_store, reset_orchestrate_singletons
    from tools.child_resume import ChildResumeInput, run_child_resume
    from tools.child_run import ChildRunInput, run_child_run
    from tools.child_status import ChildStatusInput, run_child_status
    from tools.product import ProductItem, ProductOutput
    from tools.repair_dom import RepairDomInput, run_repair_dom

    reset_orchestrate_singletons()
    parent_run = "parent-e2e-1"
    live_hub.open_run(parent_run)
    os.environ["DINGDA_AGENT_RUN_ID"] = parent_run
    os.environ["DINGDA_AGENT_RUNTIME"] = "codex"
    os.environ["DINGDA_REPAIR_OWNER"] = "parent"

    phases: list[str] = []

    with patch("cli.subagent.run_cli", new=_fake_worker_run_cli):
        run_out = await run_child_run(ChildRunInput(task="搜闲鱼露营椅"))
    phases.append(run_out.phase)
    status1 = await run_child_status(ChildStatusInput(run_id=run_out.run_id))
    status_by_session = await run_child_status(
        ChildStatusInput(session_id=run_out.session_id)
    )

    async def _fake_product(*_a: Any, **_k: Any) -> ProductOutput:
        return ProductOutput(
            ok=True,
            platform="xianyu",
            item_id="731",
            item=ProductItem(
                item_id="731",
                title="露营椅",
                price="99",
                url="https://www.goofish.com/item?id=731",
            ),
        )

    # repair_dom 函数内 ``from tools.product import run_product``，patch 源模块
    with patch("tools.product.run_product", new=_fake_product):
        repair_out = await run_repair_dom(
            RepairDomInput(
                platform="xianyu",
                item_id="731",
                url="https://www.goofish.com/item?id=731",
                worker_run_id=run_out.run_id,
            )
        )
    store = get_run_store()
    after_repair = store.get(run_out.run_id)
    after_repair_phase = str(after_repair.phase) if after_repair else "missing"
    phases.append(after_repair_phase)

    with patch("cli.subagent.run_cli", new=_fake_resume_run_cli):
        resume_out = await run_child_resume(
            ChildResumeInput(
                session_id=run_out.session_id or "ses_worker_e2e",
                message="DOM 已修复，请从中断处继续取证",
                run_id=run_out.run_id,
            )
        )
    phases.append(str(resume_out.phase))

    live_events = list(live_hub.drain(parent_run))
    phase_events = [e for e in live_events if e.get("type") == "agentPhase"]
    final = store.get(run_out.run_id)

    ok = (
        str(run_out.phase) == "needs_repair"
        and run_out.error_code == "crawler.needs_repair"
        and isinstance(run_out.repair, dict)
        and run_out.repair.get("item_id") == "731"
        and bool(run_out.session_id)
        and status1.found is True
        and status1.phase == "needs_repair"
        and status_by_session.found is True
        and status_by_session.run_id == run_out.run_id
        and repair_out.ok is True
        and after_repair_phase == "resuming"
        and resume_out.ok is True
        and str(resume_out.phase) == "completed"
        and final is not None
        and str(final.phase) == "completed"
        and len(phase_events) >= 1
    )
    checks = {
        "run_phase": str(run_out.phase) == "needs_repair",
        "error_code": run_out.error_code == "crawler.needs_repair",
        "repair_item": isinstance(run_out.repair, dict)
        and run_out.repair.get("item_id") == "731",
        "session": bool(run_out.session_id),
        "status1": status1.found is True and status1.phase == "needs_repair",
        "status_session": status_by_session.found is True
        and status_by_session.run_id == run_out.run_id,
        "repair_ok": repair_out.ok is True,
        "after_repair": after_repair_phase == "resuming",
        "resume": resume_out.ok is True and str(resume_out.phase) == "completed",
        "final": final is not None and str(final.phase) == "completed",
        "phase_events": len(phase_events) >= 1,
    }
    return CheckResult(
        name="handshake",
        ok=ok,
        details={
            "checks": checks,
            "phases": phases,
            "run": {
                "run_id": run_out.run_id,
                "session_id": run_out.session_id,
                "phase": run_out.phase,
                "error_code": run_out.error_code,
                "repair": run_out.repair,
            },
            "status1": {
                "found": status1.found,
                "phase": status1.phase,
                "error_code": status1.error_code,
            },
            "status_by_session_run_id": status_by_session.run_id,
            "repair_ok": repair_out.ok,
            "after_repair_phase": after_repair_phase,
            "resume": {
                "ok": resume_out.ok,
                "phase": resume_out.phase,
                "summary": (resume_out.summary or "")[:120],
            },
            "agent_phase_events": len(phase_events),
            "final_phase": str(final.phase) if final else None,
        },
    )


async def _check_cancel() -> CheckResult:
    """child_cancel 能把 Store 标成 cancelled。"""
    from cli.lifecycle import AgentPhase
    from cli.registry import get_run_store, reset_orchestrate_singletons
    from tools.child_cancel import ChildCancelInput, run_child_cancel
    from tools.child_run import ChildRunInput, run_child_run

    reset_orchestrate_singletons()
    os.environ["DINGDA_AGENT_RUN_ID"] = "parent-cancel"
    os.environ["DINGDA_AGENT_RUNTIME"] = "codex"

    with patch("cli.subagent.run_cli", new=_fake_cancel_run_cli):
        # 同步跑完假流；再 cancel 已结束的 run 也应安全
        run_out = await run_child_run(ChildRunInput(task="可取消任务"))
    cancel_out = await run_child_cancel(ChildCancelInput(run_id=run_out.run_id))
    snap = get_run_store().get(run_out.run_id)
    # 已 completed 的 run：cancel 不强制改写终态；另测 running→cancelled
    reset_orchestrate_singletons()
    store = get_run_store()
    from cli.lifecycle import AgentRunSnapshot

    store.upsert(
        AgentRunSnapshot(
            run_id="running-1",
            role="worker",
            phase=AgentPhase.RUNNING,
            parent_run_id="parent-cancel",
            task="x",
        )
    )
    with patch("cli.subagent.cancel_run", new=AsyncMock()):
        cancel2 = await run_child_cancel(ChildCancelInput(run_id="running-1"))
    after = store.get("running-1")
    ok = (
        cancel_out.ok
        and snap is not None
        and cancel2.ok
        and after is not None
        and after.phase == AgentPhase.CANCELLED
    )
    return CheckResult(
        name="cancel",
        ok=ok,
        details={
            "finished_run_phase": str(snap.phase) if snap else None,
            "running_cancelled": str(after.phase) if after else None,
        },
    )


async def _run() -> list[CheckResult]:
    """跑全部检查。"""
    return [
        _check_role_surfaces(),
        _check_tool_registry(),
        _check_repair_owner(),
        await _check_handshake(),
        await _check_cancel(),
    ]


def main() -> int:
    """入口：打印 JSON，全部通过返回 0。"""
    results = asyncio.run(_run())
    payload = {
        "ok": all(row.ok for row in results),
        "results": [asdict(row) for row in results],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    for row in results:
        mark = "PASS" if row.ok else "FAIL"
        logger.info("%s %s %s", mark, row.name, row.details)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
