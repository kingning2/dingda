"""WSS 运行时包。

再导出连接管理器，供 IPC handler 与自动回复链路使用。"""

from runtime.wss.manager import WssManager, get_wss_manager

__all__ = ["WssManager", "get_wss_manager"]
