"""闲鱼 session / mtop 单测（不启真实网络与浏览器）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.channels.xianyu.mtop import _classify_error, call as mtop_call
from src.channels.xianyu.session import Session
from src.shared.errors import AppError


def test_session_from_cookie_header(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.channels.xianyu.session._device_cache_path",
        lambda: tmp_path / "device.json",
    )
    with patch("src.channels.xianyu.session.generate_device_id", return_value="dev-1"):
        session = Session.from_cookie_header("unb=u1; _m_h5_tk=tok_123; cookie2=c2")
    assert session.unb == "u1"
    assert session.h5_token == "tok"
    assert session.device_id == "dev-1"


def test_session_missing_fields() -> None:
    with pytest.raises(AppError) as exc:
        Session.from_cookie_header("unb=only")
    assert exc.value.code == "account.session_expired"


def test_classify_risk() -> None:
    with pytest.raises(AppError) as exc:
        _classify_error({"ret": ["RGV587_ERROR::punish"]}, "api.x")
    assert exc.value.code == "channel.risk"


def test_classify_auth() -> None:
    with pytest.raises(AppError) as exc:
        _classify_error({"ret": ["FAIL_SYS_SESSION_EXPIRED"]}, "api.x")
    assert exc.value.code == "account.session_expired"


def test_mtop_call_success() -> None:
    http = requests.Session()
    http.cookies.update({"_m_h5_tk": "tok_abc", "unb": "u"})
    http.post = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(json=lambda: {"ret": ["SUCCESS::调用成功"], "data": {}})
    )
    session = Session(http=http, unb="u", tracknick="", device_id="d")
    with patch("src.channels.xianyu.mtop.generate_sign", return_value="sig"):
        raw = mtop_call(session, "mtop.test", {}, auto_refresh=False)
    assert raw["ret"][0].startswith("SUCCESS")
    http.post.assert_called_once()
