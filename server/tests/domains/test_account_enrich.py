"""账号资料补全测试。"""

from __future__ import annotations

from unittest.mock import patch

from src.domains.account.enrich import enrich_account_profile
from src.infrastructure.db import accounts as account_repo
from src.infrastructure.db.session import set_db_path


def test_enrich_updates_xianyu_profile(tmp_path) -> None:
    set_db_path(tmp_path / "enrich.db")
    account_repo.upsert_account(
        account_id="xy:enrich",
        platform="xianyu",
        display_name="旧名称",
        cookie="unb=1; _m_h5_tk=t; cookie2=c",
        connected=True,
    )

    with patch(
        "src.domains.account.enrich.xianyu_profile",
        return_value=("新昵称", "https://img.test/avatar.png"),
    ):
        updated = enrich_account_profile(
            "xy:enrich",
            platform="xianyu",
            cookie="unb=1; _m_h5_tk=t; cookie2=c",
        )

    assert updated is True
    row = account_repo.get_account("xy:enrich")
    assert row is not None
    assert row.display_name == "新昵称"
    assert row.avatar_url == "https://img.test/avatar.png"
