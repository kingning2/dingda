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
from pathlib import Path
from typing import Any

logger = logging.getLogger("dingda.agent.runtimes.mcp")

SERVER_NAME = "dingda"


def server_dir() -> Path:
    """定位 dingda server 根目录。"""
    env = os.getenv("DINGDA_SERVER_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]


def dingda_mcp_command() -> list[str] | None:
    """MCP stdio 启动命令：打包态用 Python 模块，开发态用 uv。"""
    root = server_dir()
    if not root.is_dir():
        logger.warning("skip mcp inject: server dir missing %s", root)
        return None

    python = (os.getenv("DINGDA_PYTHON") or "").strip()
    if python:
        return [python, "-m", "src.mcp.server"]

    uv = (os.getenv("DINGDA_UV") or "").strip() or "uv"
    server = str(root).replace("\\", "/")
    return [uv, "run", "--directory", server, "dingda-mcp"]


def dingda_mcp_uv_command() -> list[str] | None:
    """兼容旧名：同 ``dingda_mcp_command``。"""
    return dingda_mcp_command()


def _mcp_env(*, run_id: str | None, api_base: str | None) -> dict[str, str]:
    env: dict[str, str] = {"PYTHONUTF8": "1"}
    if run_id and run_id.strip():
        env["DINGDA_AGENT_RUN_ID"] = run_id.strip()
    base = (api_base or os.getenv("DINGDA_API_BASE", "") or "http://127.0.0.1:8787").strip()
    if base:
        env["DINGDA_API_BASE"] = base.rstrip("/")
    server = str(server_dir())
    env["DINGDA_SERVER_DIR"] = server
    for key in ("DINGDA_PYTHON", "DINGDA_UV", "DINGDA_CAMOUFOX_EXE", "UV_PROJECT_ENVIRONMENT"):
        value = (os.getenv(key) or "").strip()
        if value:
            env[key] = value
    return env


def stdio_mcp_entry(
    *,
    run_id: str | None = None,
    api_base: str | None = None,
) -> dict[str, Any] | None:
    """Claude / Cursor 等共用的 stdio MCP 条目。"""
    command = dingda_mcp_command()
    if not command:
        return None
    return {
        "command": command[0],
        "args": command[1:],
        "env": _mcp_env(run_id=run_id, api_base=api_base),
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


def _codex_env_override(env: dict[str, str]) -> str:
    """Codex ``-c`` 里的 env 片段。"""
    parts: list[str] = []
    for key, value in env.items():
        safe = value.replace("\\", "/").replace('"', '\\"')
        parts.append(f'"{key}"="{safe}"')
    inner = ",".join(parts)
    return f"{{{inner}}}"


def apply_mcp_inject(
    mode: str,
    *,
    cwd: Path,
    args: list[str],
    env: dict[str, str],
    run_id: str | None = None,
    api_base: str | None = None,
) -> list[str]:
    """按模式注入；返回可能被改写的 args（codex -c）。"""
    entry = stdio_mcp_entry(run_id=run_id, api_base=api_base)
    if entry is None or mode in {"", "none"}:
        return args

    for key, value in _mcp_env(run_id=run_id, api_base=api_base).items():
        env[key] = value

    if mode == "claude-mcp-json":
        _merge_mcp_servers_file(cwd / ".mcp.json", entry)
        return args

    if mode == "codex-mcp":
        command = dingda_mcp_command()
        if not command:
            return args
        mcp_env = _mcp_env(run_id=run_id, api_base=api_base)
        args_json = ",".join(f'"{part.replace(chr(92), "/")}"' for part in command[1:])
        override = (
            f'mcp_servers.{SERVER_NAME}={{'
            f'"command"="{command[0].replace(chr(92), "/")}",'
            f'"args"=[{args_json}],'
            f'"env"={_codex_env_override(mcp_env)}'
            f"}}"
        )
        if args[:2] == ["exec", "resume"]:
            out = ["exec", "resume", "-c", override, *args[2:]]
        elif args[:1] == ["exec"]:
            out = ["exec", "-c", override, *args[1:]]
        else:
            out = ["-c", override, *args]
        logger.debug("mcp inject codex -c override run=%s", run_id or "-")
        return out

    if mode == "opencode-env-content":
        command = dingda_mcp_command()
        if not command:
            return args
        mcp_env = _mcp_env(run_id=run_id, api_base=api_base)
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
