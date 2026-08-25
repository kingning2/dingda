"""Sidecar HTTP server — 兼容层，委托 ``runtime.server``。

保留旧 ``sidecar.server`` 导入路径，实现位于 runtime。"""

from runtime.server import RuntimeHandler, serve

__all__ = ["RuntimeHandler", "serve"]

# 历史名称兼容
SidecarHandler = RuntimeHandler
