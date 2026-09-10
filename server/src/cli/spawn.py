"""CLI Runtime 启动入口。

职责：
    给调用方一个稳定的 ``run_cli`` / ``cancel_run``：按 id 取插头
    （[base.py](base.py) 的 ``CliRuntime``）再起会话。
    真正的生命周期在 ``CliRuntime.run``，本文件只做分发。

设计说明：
    - 调用方（api/agent.py、repair_spawn）不需要知道插头长什么样
    - 加新 CLI：写 ``runtimes/<id>.py`` 插头 + 在 registry 登记一行

使用示例：
    async for event in run_cli("codex", "搜闲鱼露营椅", run_id="run-1"):
        ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.cli.base import cancel_run
from src.cli.registry import get_runtime, list_runtime_ids
from src.cli.roles.base import AgentRole
from src.shared.errors import AppError

__all__ = ["run_cli", "cancel_run"]


async def run_cli(
    runtime_id: str,
    prompt: str,
    *,
    run_id: str | None = None,
    cwd: str | None = None,
    model_id: str | None = None,
    session_id: str | None = None,
    reasoning: str | None = None,
    executable: str | None = None,
    extra_allowed_dirs: list[str] | None = None,
    platform_hint: str | None = None,
    role: str | AgentRole | None = None,
    mcp_env: dict[str, str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """按 id 取插头，起一次 CLI 会话并 yield AgentEvent dict。

    ``role``：``"parent"``（默认，选品父 agent）或 ``"child"``（单一职责子 agent）。
    ``mcp_env``：本次运行才有的 MCP 追加环境，叠在角色之上。
    """
    try:
        runtime = get_runtime(runtime_id)
    except KeyError as exc:
        supported = "/".join(list_runtime_ids())
        raise AppError(
            "agent.runtime_unsupported",
            f"Python 侧暂未接入 runtime：{runtime_id}（当前支持 {supported}）",
            status_code=501,
        ) from exc

    async for event in runtime.run(
        prompt,
        run_id=run_id,
        cwd=cwd,
        model_id=model_id,
        session_id=session_id,
        reasoning=reasoning,
        executable=executable,
        extra_allowed_dirs=extra_allowed_dirs,
        platform_hint=platform_hint,
        role=role,
        mcp_env=mcp_env,
    ):
        yield event
