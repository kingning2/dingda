"""组件生命周期抽象 — 全仓库唯一定义。

任何需要启停 / 状态管理的子 runtime 实现 [`Component`] 并注册进
[`dingda_sidecar.runtime.runtime.AppRuntime`]（Python 侧 supervisor）；
启停顺序、异常隔离、状态聚合由 supervisor 统一负责，
不得在组件内部另建生命周期管理。
状态取值与契约 `runtime/component_state`（Rust `ComponentState`）对齐，
经事件推送后 Rust 侧可直接消费。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict

from dingda_sidecar.runtime.context import RuntimeContext

# 与 contracts/gen/runtime.py 的 RuntimeComponentState 保持一致。
ComponentState = Literal[
    "created",
    "starting",
    "running",
    "degraded",
    "stopping",
    "stopped",
    "failed",
]


class ComponentStatus(TypedDict, total=False):
    """组件状态快照（`status()` 返回值的最小约定）。"""

    state: ComponentState
    detail: str


class Component(ABC):
    """子 runtime 组件基类 — 子类填 `name`，实现 start / stop / status。"""

    #: 组件标识（如 "agent" / "wss"），supervisor 日志与状态聚合用。
    name: str

    #: 启停守卫由基类持有的标志；子类通过 `mark_started` / `mark_stopped` 维护。
    _component_started: bool = False

    @abstractmethod
    def start(self, ctx: RuntimeContext) -> None:
        """启动组件（幂等：已启动直接返回）。"""

    @abstractmethod
    def stop(self) -> None:
        """停止组件（幂等；重复调用为无操作）。"""

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """状态快照；至少含 `state` 键。"""

    # ── 基类提供的生命周期状态辅助 ──

    def mark_started(self) -> None:
        self._component_started = True

    def mark_stopped(self) -> None:
        self._component_started = False

    def state(self) -> ComponentState:
        """由 status() 快照推断生命周期状态。"""
        reported = self.status().get("state")
        if isinstance(reported, str) and reported:
            return reported  # type: ignore[no-any-return]
        return "running" if self._component_started else "stopped"
