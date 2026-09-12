"""闲鱼风控判定测试。"""

from __future__ import annotations

from channels.xianyu.risk import is_risk_control_text, page_is_punish


def test_page_is_punish() -> None:
    assert page_is_punish("https://passport.taobao.com/_____tmd_____/punish")
    assert not page_is_punish("https://www.goofish.com/login")


def test_is_risk_control_text() -> None:
    assert is_risk_control_text("FAIL_SYS_USER_VALIDATE::需要验证")
    assert not is_risk_control_text("ok")
