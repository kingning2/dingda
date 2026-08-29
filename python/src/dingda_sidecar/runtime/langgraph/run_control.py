"""进程内 GraphRun 注册表 — pause / cancel / seek / restart 门控。"""

from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeModel:
    node: str
    base_url: str
    api_key: str
    model: str
    account_id: str = ""
    provider_type: str = ""


@dataclass
class StepRecord:
    node: str
    index: int
    status: str
    label: str = ""
    detail: str = ""
    error_kind: str = ""
    account_id: str = ""
    model: str = ""
    content: str = ""
    state_before_json: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "index": self.index,
            "status": self.status,
            "label": self.label,
            "detail": self.detail,
            "error_kind": self.error_kind,
            "account_id": self.account_id,
            "model": self.model,
            "content": self.content,
            "state_before_json": self.state_before_json,
        }


@dataclass
class GraphRun:
    run_id: str
    kind: str
    user: str
    system: str
    initial_state: dict[str, Any]
    state: dict[str, Any]
    node_models: dict[str, NodeModel]
    default_model: NodeModel | None
    steps_order: tuple[str, ...]
    status: str = "running"  # running|paused|completed|failed|cancelled
    cursor: int = 0
    completed_nodes: list[str] = field(default_factory=list)
    steps: list[StepRecord] = field(default_factory=list)
    state_before: dict[str, dict[str, Any]] = field(default_factory=dict)
    reply: str = ""
    error: str = ""
    error_kind: str = ""
    failed_node: str = ""
    paused: threading.Event = field(default_factory=threading.Event)
    cancelled: threading.Event = field(default_factory=threading.Event)
    wake: threading.Event = field(default_factory=threading.Event)
    pending_action: str | None = None  # continue|restart|seek
    pending_seek_node: str | None = None
    pending_node_model: NodeModel | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        # paused Event: set = paused waiting; clear = running
        self.paused.clear()
        self.cancelled.clear()
        self.wake.set()

    def snapshot(self, *, since_index: int = 0) -> dict[str, Any]:
        with self.lock:
            steps = [s.to_dict() for s in self.steps if s.index >= since_index]
            current = (
                self.steps_order[self.cursor] if 0 <= self.cursor < len(self.steps_order) else ""
            )
            return {
                "ok": True,
                "run_id": self.run_id,
                "state": self.status,
                "current_node": current,
                "completed_nodes": list(self.completed_nodes),
                "steps": steps,
                "reply": self.reply,
                "error": self.error,
                "error_kind": self.error_kind,
                "failed_node": self.failed_node,
            }


class GraphRunRegistry:
    """进程内 run_id → GraphRun。"""

    def __init__(self) -> None:
        self._runs: dict[str, GraphRun] = {}
        self._lock = threading.Lock()

    def create(self, run: GraphRun) -> GraphRun:
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> GraphRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def remove(self, run_id: str) -> None:
        with self._lock:
            self._runs.pop(run_id, None)


_registry: GraphRunRegistry | None = None
_registry_lock = threading.Lock()


def get_run_registry() -> GraphRunRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = GraphRunRegistry()
    return _registry


def new_run_id() -> str:
    return uuid.uuid4().hex


def parse_node_models(raw: list[dict[str, Any]] | None) -> dict[str, NodeModel]:
    out: dict[str, NodeModel] = {}
    for item in raw or []:
        node = str(item.get("node") or "").strip()
        if not node:
            continue
        out[node] = NodeModel(
            node=node,
            base_url=str(item.get("base_url") or ""),
            api_key=str(item.get("api_key") or ""),
            model=str(item.get("model") or ""),
            account_id=str(item.get("account_id") or ""),
            provider_type=str(item.get("provider_type") or ""),
        )
    return out


def dumps_state(state: dict[str, Any]) -> str:
    try:
        return json.dumps(state, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return "{}"


def loads_state(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def deep_copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


def now_ms() -> int:
    return int(time.time() * 1000)
