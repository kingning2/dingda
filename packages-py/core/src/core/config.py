"""应用配置模块。

职责：
    定义并加载后端运行所需的全部配置项，统一从以下来源合并：
    1. 命令行参数（由 ``__main__`` 传入）
    2. 环境变量（``DINGDA_HOST``、``DINGDA_PORT``、``DINGDA_LOG_LEVEL`` 等）
    3. 代码内默认值
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """后端全局配置快照。"""

    host: str = "127.0.0.1"
    port: int = 8787
    log_level: str = "INFO"
    reload: bool = False

    @classmethod
    def from_env(
        cls,
        *,
        host: str | None = None,
        port: int | None = None,
        log_level: str | None = None,
        reload: bool | None = None,
    ) -> Settings:
        """合并 CLI 参数与环境变量，生成配置实例。"""
        return cls(
            host=host or os.getenv("DINGDA_HOST", "127.0.0.1"),
            port=port or int(os.getenv("DINGDA_PORT", "8787")),
            log_level=(log_level or os.getenv("DINGDA_LOG_LEVEL", "INFO")).upper(),
            reload=reload
            if reload is not None
            else os.getenv("DINGDA_RELOAD", "").strip() in {"1", "true", "yes"},
        )
