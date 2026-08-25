"""Python Runtime — HTTP 服务、IPC 路由与生命周期。

再导出 lifecycle / server，供 sidecar 入口与 Rust 托管进程使用。"""

from runtime.lifecycle import RuntimeLifecycle
from runtime.server import serve

__all__ = ["RuntimeLifecycle", "serve"]
