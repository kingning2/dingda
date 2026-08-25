"""Sidecar route table — 兼容层，委托 ``runtime.ipc``。

旧代码从本模块导入路由表时，实际指向统一 IPC 注册表。"""

from runtime.ipc import HANDLERS, ROUTES

__all__ = ["HANDLERS", "ROUTES"]
