"""壳层 bootstrap 与后端预热状态机测试。

职责：
    钉死「什么会推进 phase」这条契约 —— ``/health`` 只回报 phase 而不触发预热，
    只有 ``/v1/bootstrap`` 才把后端从 ``shell`` 推到 ``ready``。

设计说明：
    - Rust 壳层靠 ``/health`` 探活，所以它永远看不到 ``ready``，这是设计而非缺陷。
      桌面端白屏那次据此误判成"后端没预热"，真实原因是前端没加载、从未调用
      ``/v1/bootstrap``（来龙去脉见 ``e2e/README.md`` 的「为什么窗口会白屏」）
    - ``_phase`` / ``_warm_task`` 是模块级全局：不重置的话，先跑的用例预热完成后，
      后续用例看到的 phase 全是 ``ready``，前一个测试会静默污染后一个
    - 预热会真的建 SQLite 表，故把库路径指到 ``tmp_path``，
      不落 ``~/.dingda/v2/dingda.db``
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.boot import warmup
from infrastructure.db import session as db_session


@pytest.fixture(autouse=True)
def _isolate_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    """重置预热全局状态，让每个用例都从 shell 起步。"""
    monkeypatch.setattr(warmup, "_phase", warmup.WarmupPhase.SHELL, raising=False)
    monkeypatch.setattr(warmup, "_warm_task", None, raising=False)
    # 锁是 import 期创建的，TestClient 每次请求可能跑在不同的事件循环上，
    # 换一把新的避免跨循环绑定
    monkeypatch.setattr(warmup, "_lock", asyncio.Lock(), raising=False)


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """把 SQLite 指到临时目录，避免预热建表污染真实数据目录。"""
    monkeypatch.setattr(db_session, "_db_path", tmp_path / "test.db", raising=False)


def test_health_reports_shell_phase_before_warmup(client: TestClient) -> None:
    """壳层首次探活应看到 shell。"""
    body = client.get("/health").json()

    assert body == {"status": "ok", "phase": "shell"}


def test_health_does_not_advance_phase(client: TestClient) -> None:
    """反复探活不得推进 phase —— 探活只读，预热只能由前端触发。"""
    for _ in range(3):
        assert client.get("/health").json()["phase"] == "shell"

    assert warmup.current_phase() == "shell"


def test_bootstrap_snapshots_then_warms_to_ready(client: TestClient) -> None:
    """bootstrap 先按当前 phase 出快照，再在后台把后端推到 ready。"""
    body = client.get("/v1/bootstrap").json()

    # 响应体是**触发预热前**拍的快照，所以仍是 shell
    assert body["phase"] == "shell"
    assert body["runtime"]["phase"] == "shell"
    # TestClient 会等后台任务跑完，故此刻全局已 ready
    assert warmup.current_phase() == "ready"
    assert client.get("/health").json()["phase"] == "ready"


def test_bootstrap_second_poll_sees_ready(client: TestClient) -> None:
    """前端轮询语义：第二次 bootstrap 必须看到 ready。"""
    client.get("/v1/bootstrap")

    body = client.get("/v1/bootstrap").json()

    assert body["phase"] == "ready"
    assert body["runtime"]["phase"] == "ready"


def test_bootstrap_snapshot_shape(client: TestClient) -> None:
    """快照字段是壳层首屏契约，改形状必须让这个用例先失败。"""
    body = client.get("/v1/bootstrap").json()

    assert body["ok"] is True
    assert body["capabilities"] == ["health", "runtime", "bootstrap"]
    assert body["runtime"]["ok"] is True
    assert body["runtime"]["state"] == "running"
    assert isinstance(body["runtime"]["uptime_ms"], int)
