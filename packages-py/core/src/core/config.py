"""应用配置模块。

职责：
    定义并加载后端运行所需的全部配置项，统一从以下来源合并：
    1. 命令行参数（由 ``__main__`` 传入）
    2. 环境变量（``DINGDA_HOST``、``DINGDA_PORT``、``DINGDA_LOG_LEVEL`` 等）
    3. ``.env`` 文件（``load_dotenv_file``：Server 侧加载，真实环境变量优先）
    4. 代码内默认值
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv_file(directory: Path | None = None) -> None:
    """把 ``<目录>/.env`` 的 KEY=VALUE 注入进程环境，真实环境变量优先不覆盖。

    外部 CLI 删除后这里是 Server 读 ``.env`` 的唯一入口：``__main__`` 在读任何
    配置之前调用；工具/修复子进程由 Server 派生，继承已注入的环境。
    锚点优先 ``DINGDA_SERVER_DIR``（桌面壳注入），否则用当前工作目录。
    """
    anchor = Path(directory or os.getenv("DINGDA_SERVER_DIR") or Path.cwd())
    path = anchor / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip()


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
