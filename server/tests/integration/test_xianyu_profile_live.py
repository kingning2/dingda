"""闲鱼资料拉取：用本机已登录账号 cookie 打真实 mtop。"""

from __future__ import annotations

import pytest

from src.channels.cookie_header import parse_cookie_header
from src.channels.xianyu.refresh import _REQUIRED_COOKIES, nav_profile
from src.infrastructure.db import accounts as account_repo
from src.infrastructure.db.session import data_dir, set_db_path


def _logged_in_xianyu_cookie() -> str:
    """从 ~/.dingda/v2/dingda.db 取出一条可用闲鱼 cookie。"""
    set_db_path(data_dir() / "dingda.db")
    rows = account_repo.list_accounts(platform="xianyu")
    for row in rows:
        cookie = (row.cookie or "").strip()
        if not cookie:
            continue
        parsed = parse_cookie_header(cookie)
        if all(parsed.get(key) for key in _REQUIRED_COOKIES):
            return cookie
    pytest.skip("本机没有已登录的闲鱼账号（缺 unb / _m_h5_tk / cookie2）")


@pytest.mark.integration
def test_profile_live_logged_in_session() -> None:
    """用已登录 session 拉昵称和头像，对齐 main 的 user.page.nav。"""
    cookie = _logged_in_xianyu_cookie()
    page = nav_profile(cookie)
    assert page.display_name, f"昵称为空 page={page!r}"
    assert page.avatar_url, f"头像为空 page={page!r}"
    assert page.avatar_url.startswith("http")
    assert page.followers is not None
    assert page.following is not None
