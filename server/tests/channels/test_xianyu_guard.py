"""闲鱼 limiter / guard 单测（落临时数据目录）。"""

from __future__ import annotations

import pytest

from src.channels.xianyu import guard, limiter
from src.shared.errors import AppError, rate_limited_error, risk_control_error


def test_limiter_acquire_then_block(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(limiter, "_state_path", lambda: tmp_path / "limiter.json")
    monkeypatch.setenv("DINGDA_WRITE_RPM", "1")
    with limiter.acquire("item.write"):
        pass
    with pytest.raises(AppError) as exc:
        limiter.check("item.write")
    assert exc.value.code == "channel.rate_limited"


def test_rate_limited_error_shape() -> None:
    err = rate_limited_error("再等 1s")
    assert err.code == "channel.rate_limited"
    assert err.status_code == 429


def test_guard_trip_then_check(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(guard, "_state_path", lambda: tmp_path / "circuit.json")
    monkeypatch.setenv("DINGDA_CIRCUIT_BREAK_MINUTES", "1")
    guard.trip()
    with pytest.raises(AppError) as exc:
        guard.check()
    assert exc.value.code == "channel.risk"
    guard.reset()
    guard.check()


def test_guard_hold_trips_on_risk(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(guard, "_state_path", lambda: tmp_path / "circuit.json")
    monkeypatch.setenv("DINGDA_CIRCUIT_BREAK_MINUTES", "1")
    with pytest.raises(AppError) as exc:
        with guard.hold():
            raise risk_control_error("RGV587")
    assert exc.value.code == "channel.risk"
    with pytest.raises(AppError) as blocked:
        guard.check()
    assert "熔断" in blocked.value.message
