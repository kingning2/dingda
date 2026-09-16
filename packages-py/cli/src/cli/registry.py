"""子会话编排注册表。

职责：
    提供 ``get_subagent_session`` / ``get_run_store`` 单例入口。
"""

from __future__ import annotations

from cli.runs import AgentRunStore, MemoryAgentRunStore
from cli.subagent import CliSubAgentSession, SubAgentSession

_STORE: AgentRunStore | None = None
_SESSION: SubAgentSession | None = None


def get_run_store() -> AgentRunStore:
    """进程内 RunStore 单例。"""
    global _STORE
    if _STORE is None:
        _STORE = MemoryAgentRunStore()
    return _STORE


def get_subagent_session() -> SubAgentSession:
    """子会话插座单例（v1 = CLI 插头）。"""
    global _SESSION
    if _SESSION is None:
        _SESSION = CliSubAgentSession(store=get_run_store())
    return _SESSION


def reset_orchestrate_singletons() -> None:
    """测试用：清掉单例。"""
    global _STORE, _SESSION
    _STORE = None
    _SESSION = None
