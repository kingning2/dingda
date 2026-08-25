"""Sidecar HTTP server — 兼容层，委托 runtime.server。"""

from runtime.server import RuntimeHandler, serve

__all__ = ["RuntimeHandler", "serve"]

# 历史名称兼容
SidecarHandler = RuntimeHandler
