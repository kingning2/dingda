"""应用配置模块。

职责：
    定义并加载后端运行所需的全部配置项，统一从以下来源合并（后者被前者覆盖）：
    1. 代码内默认值
    2. 仓库根的 `.env`（模板见根目录 `.env.example`，由 ``load_env()`` 加载）
    3. 真实环境变量（CI / E2E 的临时覆盖）
    4. 命令行参数（由 ``__main__`` 传入）

设计说明：
    - ``api_base_url()`` 是「当前 Server 的 HTTP 基址」的**唯一来源**：桌面壳只注入
      ``DINGDA_PORT``，写死常量就会漂移 —— 曾经硬编码 8787，导致换端口后直播帧被
      推去错误端口并静默丢弃。
    - ``load_env()`` 必须由**入口**显式调用（``api.__main__``），不做 import 副作用；
      壳拉起的子进程会继承 ``os.environ``，所以加载一次即可。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def _env_port() -> int:
    """``DINGDA_PORT`` 的容错解析：空值 / 非法值回落默认端口。

    壳的 Rust 侧（``PythonConfig::from_env``）用 ``parse().ok()`` 容忍坏值，
    这里保持一致 —— 否则一个空的 ``DINGDA_PORT`` 会让整个 Server 起不来。
    """
    raw = os.getenv("DINGDA_PORT", "").strip()
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


@dataclass(frozen=True, slots=True)
class Settings:
    """后端全局配置快照。"""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
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
            host=host or os.getenv("DINGDA_HOST", DEFAULT_HOST),
            port=port or _env_port(),
            log_level=(log_level or os.getenv("DINGDA_LOG_LEVEL", "INFO")).upper(),
            reload=reload
            if reload is not None
            else os.getenv("DINGDA_RELOAD", "").strip() in {"1", "true", "yes"},
        )


def api_base_url() -> str:
    """当前 Server 的 HTTP 基址（无尾斜杠）。

    ``DINGDA_API_BASE`` 显式指定时优先；否则按 ``DINGDA_HOST`` / ``DINGDA_PORT``
    拼 —— 桌面壳只注入 ``DINGDA_PORT``，不注入 ``DINGDA_API_BASE``，
    所以**不能**在这里回落到写死的端口。
    """
    explicit = os.getenv("DINGDA_API_BASE", "").strip()
    if explicit:
        return explicit.rstrip("/")
    settings = Settings.from_env()
    return f"http://{settings.host}:{settings.port}"


# ---------------------------------------------------------------------------
# `.env`（仓库根，模板见根目录 `.env.example`）
# ---------------------------------------------------------------------------

_ENV_LOADED = False


def _repo_root() -> Path | None:
    """仓库根：``DINGDA_SERVER_DIR`` 优先，否则从本文件向上找 workspace marker。

    壳在开发态把 ``DINGDA_SERVER_DIR`` 指向仓库根、安装包指向可写工作副本，
    两种情况 `.env` 都在那个目录下。
    """
    explicit = os.getenv("DINGDA_SERVER_DIR", "").strip()
    if explicit:
        return Path(explicit)
    for parent in Path(__file__).resolve().parents:
        if (parent / "uv.lock").is_file() and (parent / "packages-py").is_dir():
            return parent
    return None


def env_file() -> Path | None:
    """`.env` 的路径；不存在返回 None。可用 ``DINGDA_ENV_FILE`` 显式指定。"""
    explicit = os.getenv("DINGDA_ENV_FILE", "").strip()
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    root = _repo_root()
    if root is None:
        return None
    path = root / ".env"
    return path if path.is_file() else None


def load_env() -> Path | None:
    """把仓库根的 `.env` 读进 ``os.environ``，返回读到的文件（没有则 None）。

    设计说明：
        - **幂等**：多次调用只加载一次，三条入口重复调也安全
        - **不覆盖**已存在的真实环境变量 —— CI / E2E 的临时覆盖必须优先于 `.env`
        - 放在 ``core`` 是因为 Server、工具子进程、CLI 都 import 它，
          这样三处读到的是同一份配置；壳拉起的子进程还会继承 ``os.environ``

    使用示例：
        load_env()
        settings = Settings.from_env()
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return env_file()
    _ENV_LOADED = True
    path = env_file()
    if path is None:
        return None
    load_dotenv(path, override=False)
    return path
