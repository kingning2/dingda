"""外部 CLI 的 dingda-mcp 进程级注入。

职责：
    按 MCP 模式写入 cwd 配置或拼 CLI 覆盖参数，不改用户全局配置。
    注入 ``DINGDA_AGENT_RUN_ID`` / ``DINGDA_API_BASE`` 供 preview 推帧。

设计说明：
    - 优先 ``DINGDA_PYTHON -m src.mcp.server``（桌面打包态）
    - 其次 ``DINGDA_UV`` / ``uv run --directory <server> dingda-mcp``（开发态）
    - server 目录：``DINGDA_SERVER_DIR`` 或本包上溯到 ``server/``
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("dingda.cli.mcp")

SERVER_NAME = "dingda"
# 冷启动（uv run 首次解析环境）可能超过 codex 默认的 10s，给足
CODEX_MCP_STARTUP_TIMEOUT_S = 30


def server_dir() -> Path:
    """定位 dingda server 根目录。"""
    env = os.getenv("DINGDA_SERVER_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]


def dingda_mcp_command() -> list[str] | None:
    """MCP stdio 启动命令：**必须给绝对解释器**。

    codex / claude 拉起 MCP 子进程时的 PATH 往往比我们的 shell 窄，裸 ``uv``
    会直接 ``MCP startup failed: 系统找不到指定的路径 (os error 3)``（codex 的
    ``rmcp_client`` 日志里能看到）。所以优先用绝对路径的解释器。
    """
    root = server_dir()
    if not root.is_dir():
        logger.warning("skip mcp inject: server dir missing %s", root)
        return None

    python = (os.getenv("DINGDA_PYTHON") or "").strip()
    if python:
        return [python, "-m", "src.mcp.server"]
    if sys.executable and Path(sys.executable).is_file():
        # 开发态：当前解释器就是跑 server 的那个
        return [str(Path(sys.executable).resolve()), "-m", "src.mcp.server"]

    uv = (os.getenv("DINGDA_UV") or "").strip() or "uv"
    server = str(root).replace("\\", "/")
    return [uv, "run", "--directory", server, "dingda-mcp"]


def dingda_mcp_uv_command() -> list[str] | None:
    """兼容旧名：同 ``dingda_mcp_command``。"""
    return dingda_mcp_command()


def _mcp_env(
    *,
    run_id: str | None,
    api_base: str | None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env: dict[str, str] = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    if run_id and run_id.strip():
        env["DINGDA_AGENT_RUN_ID"] = run_id.strip()
    base = (api_base or os.getenv("DINGDA_API_BASE", "") or "http://127.0.0.1:8787").strip()
    if base:
        env["DINGDA_API_BASE"] = base.rstrip("/")
    server = str(server_dir())
    env["DINGDA_SERVER_DIR"] = server
    # 子进程 cwd 不一定在仓库里：要让 `python -m src.mcp.server` 能找到 src
    env.setdefault("PYTHONPATH", server)
    for key in ("DINGDA_PYTHON", "DINGDA_UV", "DINGDA_CAMOUFOX_EXE", "UV_PROJECT_ENVIRONMENT"):
        value = (os.getenv(key) or "").strip()
        if value:
            env[key] = value
    # 会话级追加（如子 agent 的工具白名单、校验回打地址）
    for key, value in (extra or {}).items():
        text = str(value or "").strip()
        if text:
            env[key] = text
    return env


def stdio_mcp_entry(
    *,
    run_id: str | None = None,
    api_base: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Claude / Cursor 等共用的 stdio MCP 条目。"""
    command = dingda_mcp_command()
    if not command:
        return None
    return {
        "command": command[0],
        "args": command[1:],
        "env": _mcp_env(run_id=run_id, api_base=api_base, extra=extra_env),
    }


def _merge_mcp_servers_file(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    root: dict[str, Any]
    if path.is_file():
        try:
            root = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            root = {"mcpServers": {}}
    else:
        root = {"mcpServers": {}}
    if not isinstance(root, dict):
        root = {"mcpServers": {}}
    servers = root.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    servers[SERVER_NAME] = entry
    root["mcpServers"] = servers
    path.write_text(json.dumps(root, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("mcp inject wrote %s", path)


def _toml_str(value: str) -> str:
    """TOML 基本字符串。"""
    return '"' + str(value).replace("\\", "/").replace('"', '\\"') + '"'


def _codex_mcp_overrides(command: list[str], env: dict[str, str]) -> list[str]:
    """Codex 的 MCP 注入：**逐键点分赋值**。

    codex 的 ``-c`` 值是「一个 TOML 值」，塞整张内联表会解析失败并被当成字面字符串
    （报 ``invalid type: string ... in mcp_servers.<name>``），所以一键一个 ``-c``。
    参考 ``codex mcp --help``：dotted path 覆盖嵌套值，值按 TOML 解析。
    """
    base = f"mcp_servers.{SERVER_NAME}"
    args_json = "[" + ",".join(_toml_str(part) for part in command[1:]) + "]"
    overrides = [
        "-c",
        f"{base}.command={_toml_str(command[0])}",
        "-c",
        f"{base}.args={args_json}",
        "-c",
        f"{base}.startup_timeout_sec={CODEX_MCP_STARTUP_TIMEOUT_S}",
    ]
    for key, value in env.items():
        overrides += ["-c", f"{base}.env.{key}={_toml_str(value)}"]
    return overrides


def apply_mcp_inject(
    mode: str,
    *,
    cwd: Path,
    args: list[str],
    env: dict[str, str],
    run_id: str | None = None,
    api_base: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> list[str]:
    """按模式注入；返回可能被改写的 args（codex -c）。

    ``extra_env`` 追加到 MCP 子进程环境（子 agent 的工具白名单、校验回打地址等）。
    """
    entry = stdio_mcp_entry(run_id=run_id, api_base=api_base, extra_env=extra_env)
    if entry is None or mode in {"", "none"}:
        return args

    for key, value in _mcp_env(run_id=run_id, api_base=api_base, extra=extra_env).items():
        env[key] = value

    if mode == "claude-mcp-json":
        _merge_mcp_servers_file(cwd / ".mcp.json", entry)
        return args

    if mode == "codex-mcp":
        command = dingda_mcp_command()
        if not command:
            return args
        mcp_env = _mcp_env(run_id=run_id, api_base=api_base, extra=extra_env)
        overrides = _codex_mcp_overrides(command, mcp_env)
        if args[:2] == ["exec", "resume"]:
            out = ["exec", "resume", *overrides, *args[2:]]
        elif args[:1] == ["exec"]:
            out = ["exec", *overrides, *args[1:]]
        else:
            out = [*overrides, *args]
        logger.debug("mcp inject codex flags=%s run=%s", len(overrides), run_id or "-")
        return out

    if mode == "opencode-env-content":
        command = dingda_mcp_command()
        if not command:
            return args
        mcp_env = _mcp_env(run_id=run_id, api_base=api_base, extra=extra_env)
        content = json.dumps(
            {
                "mcp": {
                    SERVER_NAME: {
                        "type": "local",
                        "command": command,
                        "enabled": True,
                        "environment": mcp_env,
                    }
                }
            },
            ensure_ascii=False,
        )
        env["OPENCODE_CONFIG_CONTENT"] = content
        logger.debug("mcp inject OPENCODE_CONFIG_CONTENT run=%s", run_id or "-")
        return args

    logger.warning("mcp inject unknown mode=%s", mode)
    return args
