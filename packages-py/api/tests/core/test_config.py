"""Server 基址解析 + `.env` 加载测试。

重点两条回归：
1. **桌面壳只注入 `DINGDA_PORT`** —— `api_base_url()` / `tools.live_push.api_base()`
   必须跟着端口走，不能回落到写死的 8787；否则非默认端口下直播帧会被推到错误端口
   并静默丢弃。
2. **`.env` 的优先级**：真实环境变量 > `.env` > 代码默认值。
"""

from __future__ import annotations

import pathlib

import pytest

import core.config as config_module
from cli.base import _api_base
from core.config import DEFAULT_PORT, api_base_url, env_file, load_env
from tools.live_push import api_base


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """把所有配置来源都清干净，避免宿主环境串味。"""
    for key in (
        "DINGDA_API_BASE",
        "VITE_API_BASE_URL",
        "DINGDA_HOST",
        "DINGDA_PORT",
        "DINGDA_ENV_FILE",
        "DINGDA_SERVER_DIR",
        "DINGDA_LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)
    # `load_env()` 是进程级一次性加载，测不同文件时必须重置
    monkeypatch.setattr(config_module, "_ENV_LOADED", False)


def test_explicit_api_base_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式 `DINGDA_API_BASE` 优先，并去掉尾斜杠。"""
    monkeypatch.setenv("DINGDA_API_BASE", "http://127.0.0.1:7777/")
    monkeypatch.setenv("DINGDA_PORT", "9998")
    assert api_base_url() == "http://127.0.0.1:7777"


def test_follows_dingda_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """回归：换端口必须跟着换（E2E 用 8799/8801，dev 用 8787）。"""
    monkeypatch.setenv("DINGDA_PORT", "8801")
    assert api_base_url() == "http://127.0.0.1:8801"


def test_follows_dingda_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HOST", "0.0.0.0")
    monkeypatch.setenv("DINGDA_PORT", "9000")
    assert api_base_url() == "http://0.0.0.0:9000"


@pytest.mark.parametrize("bad", ["", "   ", "not-a-port"])
def test_bad_port_falls_back_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
    bad: str,
) -> None:
    """空值 / 非法值回落默认端口（与壳的 Rust 侧 `parse().ok()` 一致），不能抛。"""
    monkeypatch.setenv("DINGDA_PORT", bad)
    assert api_base_url() == f"http://127.0.0.1:{DEFAULT_PORT}"


def test_no_env_at_all_uses_default_port() -> None:
    assert api_base_url() == f"http://127.0.0.1:{DEFAULT_PORT}"


def test_cli_and_tools_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI 侧与 Tool 子进程侧必须解析出同一个地址（防两边常量漂移）。"""
    monkeypatch.setenv("DINGDA_PORT", "8801")
    assert _api_base() == api_base() == "http://127.0.0.1:8801"


def test_tools_keeps_vite_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """`VITE_API_BASE_URL` 仍排在 `DINGDA_API_BASE` 之后、推导值之前。"""
    monkeypatch.setenv("VITE_API_BASE_URL", "http://127.0.0.1:6666/")
    monkeypatch.setenv("DINGDA_PORT", "8801")
    assert api_base() == "http://127.0.0.1:6666"


# ---------------------------------------------------------------------------
# `.env` 加载（模板见仓库根 `.env.example`）
# ---------------------------------------------------------------------------


def _write_env(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def test_env_file_honours_explicit_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """`DINGDA_ENV_FILE` 可以指定任意位置的 `.env`。"""
    path = _write_env(tmp_path, "DINGDA_LOG_LEVEL=WARNING\n")
    monkeypatch.setenv("DINGDA_ENV_FILE", str(path))
    assert env_file() == path


def test_env_file_missing_path_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """指向不存在的文件时不抛错，只返回 None。"""
    monkeypatch.setenv("DINGDA_ENV_FILE", str(tmp_path / "nope.env"))
    assert env_file() is None
    assert load_env() is None


def test_env_file_falls_back_to_server_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """没给 `DINGDA_ENV_FILE` 时用 `DINGDA_SERVER_DIR` 下的 `.env`。"""
    _write_env(tmp_path, "DINGDA_LOG_LEVEL=WARNING\n")
    monkeypatch.setenv("DINGDA_SERVER_DIR", str(tmp_path))
    assert env_file() == tmp_path / ".env"


def test_load_env_feeds_os_environ(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """`.env` 里的值要真的进 `os.environ`，并被 `Settings.from_env()` 读到。"""
    path = _write_env(tmp_path, "DINGDA_LOG_LEVEL=WARNING\nDINGDA_PORT=8899\n")
    monkeypatch.setenv("DINGDA_ENV_FILE", str(path))
    assert load_env() == path
    from core.config import Settings

    settings = Settings.from_env()
    assert settings.log_level == "WARNING"
    assert settings.port == 8899
    assert api_base_url() == "http://127.0.0.1:8899"


def test_real_env_wins_over_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """回归：CI / E2E 的临时覆盖必须优先于 `.env`。"""
    path = _write_env(tmp_path, "DINGDA_LOG_LEVEL=WARNING\n")
    monkeypatch.setenv("DINGDA_ENV_FILE", str(path))
    monkeypatch.setenv("DINGDA_LOG_LEVEL", "ERROR")
    load_env()
    from core.config import Settings

    assert Settings.from_env().log_level == "ERROR"


def test_load_env_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """重复调用只加载一次，第二次改文件不会再生效（进程级一次性）。"""
    first = _write_env(tmp_path, "DINGDA_LOG_LEVEL=WARNING\n")
    monkeypatch.setenv("DINGDA_ENV_FILE", str(first))
    assert load_env() == first
    first.write_text("DINGDA_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    assert load_env() == first
    from core.config import Settings

    assert Settings.from_env().log_level == "WARNING"

