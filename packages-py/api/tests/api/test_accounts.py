"""test_accounts API 测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from channels.types import LoginSnapshot, LoginStatus
from contracts.channel import QrStartRequest
from domains.channel.qr_service import ChannelQrService
from infrastructure.db.session import set_db_path


@pytest.fixture
def account_client(tmp_path):
    set_db_path(tmp_path / "test.db")
    with TestClient(create_app()) as client:
        yield client


def test_qr_check_success_persists_account(tmp_path) -> None:
    set_db_path(tmp_path / "qr.db")
    success = LoginSnapshot(
        status=LoginStatus.SUCCESS,
        detail="登录成功！",
        account_id="xy:123",
        display_name="阿闲",
        avatar_url="https://img.test/a.png",
        cookie="unb=123; _m_h5_tk=t; cookie2=c",
    )
    channel = __import__("unittest.mock").mock.MagicMock()
    runtime = __import__("unittest.mock").mock.MagicMock()
    runtime.ready.wait.return_value = True
    channel.start_login.return_value = runtime
    channel.snapshot.return_value = success

    with patch(
        "domains.channel.qr_service.create_qr_login_channel",
        return_value=channel,
    ):
        service = ChannelQrService()
        started = service.start(QrStartRequest(platform="xianyu"))
        checked = service.check(started.session_id)  # type: ignore[arg-type]

    assert checked.status == "success"

    with TestClient(create_app()) as client:
        listed = client.get("/v1/accounts", params={"platform": "xianyu"})
    item = listed.json()["items"][0]
    assert item["account_id"] == "xy:123"
    assert item["display_name"] == "阿闲"
    assert item["avatar_url"] == "https://img.test/a.png"
    assert item["session"]["label"] == "已连接"
    assert item["actions"]["can_disconnect"] is True


def test_account_patch_and_delete(account_client: TestClient) -> None:
    from infrastructure.db import accounts as account_repo

    account_repo.upsert_account(
        account_id="xy:patch",
        platform="xianyu",
        display_name="原名",
        cookie="unb=1; _m_h5_tk=t; cookie2=c",
        auto_connect=False,
        auth_valid=True,
        connected=False,
    )

    patched = account_client.patch(
        "/v1/accounts/xy:patch",
        json={"display_name": "新名称", "auto_connect": True},
    )
    assert patched.status_code == 200
    item = patched.json()["item"]
    assert item["display_name"] == "新名称"
    assert item["auto_connect"] is True
    assert item["session"]["label"] == "未连接"
    assert item["actions"]["can_connect"] is True

    deleted = account_client.delete("/v1/accounts/xy:patch")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_account_list_reflects_auth_expired(account_client: TestClient) -> None:
    from infrastructure.db import accounts as account_repo

    account_repo.upsert_account(
        account_id="xy:expired",
        platform="xianyu",
        display_name="过期账号",
        cookie="unb=1; _m_h5_tk=t; cookie2=c",
        auth_valid=False,
    )

    listed = account_client.get("/v1/accounts", params={"platform": "xianyu"})
    item = listed.json()["items"][0]
    assert item["auth_valid"] is False
    assert item["session"]["state"] == "auth_expired"
    assert item["session"]["label"] == "登录过期"
    assert item["actions"]["can_rescan"] is True


def test_account_connect_and_disconnect(account_client: TestClient) -> None:
    from infrastructure.db import accounts as account_repo

    account_repo.upsert_account(
        account_id="xy:connect",
        platform="xianyu",
        display_name="连接测试",
        cookie="unb=1; _m_h5_tk=t; cookie2=c",
        connected=False,
    )

    connected = account_client.post("/v1/accounts/xy:connect/connect")
    assert connected.status_code == 200
    item = connected.json()["item"]
    assert item["session"]["label"] == "已连接"
    assert item["actions"]["can_disconnect"] is True

    disconnected = account_client.post("/v1/accounts/xy:connect/disconnect")
    assert disconnected.status_code == 200
    assert disconnected.json()["item"]["session"]["label"] == "未连接"


def test_account_profile_page_uses_stored_fields(account_client: TestClient) -> None:
    from infrastructure.db import accounts as account_repo

    account_repo.upsert_account(
        account_id="xy:profile",
        platform="xianyu",
        display_name="阿闲",
        cookie="unb=1; _m_h5_tk=t; cookie2=c",
        avatar_url="https://img.test/a.png",
    )
    response = account_client.get("/v1/accounts/xy:profile/profile")
    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["display_name"] == "阿闲"
    assert profile["avatar_url"] == "https://img.test/a.png"
    assert profile["followers"] is None


def test_xiaohongshu_profile_page_uses_stored_fields(account_client: TestClient) -> None:
    from infrastructure.db import accounts as account_repo

    account_repo.upsert_account(
        account_id="xhs:me",
        platform="xiaohongshu",
        display_name="小红薯",
        cookie="a1=1; web_session=s",
        avatar_url="https://img.test/xhs.png",
    )
    response = account_client.get("/v1/accounts/xhs:me/profile")
    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["display_name"] == "小红薯"
    assert profile["avatar_url"] == "https://img.test/xhs.png"
    assert profile["followers"] is None


def test_account_delete_missing(account_client: TestClient) -> None:
    response = account_client.delete("/v1/accounts/missing")
    assert response.status_code == 404


def test_ali1688_list_probe_and_delete_clears_ak(
    account_client: TestClient,
    tmp_path,
    monkeypatch,
) -> None:
    import base64

    from channels.ali1688.ak import get_ak, save_ak
    from infrastructure.db import accounts as account_repo

    monkeypatch.setattr("channels.ali1688.ak.data_dir", lambda: tmp_path)
    monkeypatch.delenv("ALI_1688_AK", raising=False)
    secret = "e" * 32
    ak_id = "list-id"
    raw = base64.urlsafe_b64encode(f"{secret}{ak_id}".encode()).decode().rstrip("=")
    save_ak(raw)
    account_repo.upsert_account(
        account_id=f"ali1688:{ak_id}",
        platform="ali1688",
        display_name="1688 AK",
        cookie=raw,
        auth_valid=True,
    )

    listed = account_client.get("/v1/accounts", params={"platform": "ali1688"})
    item = listed.json()["items"][0]
    assert item["auth_valid"] is True
    assert item["session"]["label"] == "已登录"

    # 清掉本地 AK 后再列表 → 过期
    (tmp_path / "ali1688" / "ak.json").unlink()
    listed2 = account_client.get("/v1/accounts", params={"platform": "ali1688"})
    assert listed2.json()["items"][0]["auth_valid"] is False
    assert listed2.json()["items"][0]["session"]["state"] == "auth_expired"

    # 重新写入后删除账号应清 AK
    save_ak(raw)
    account_repo.set_auth_valid(f"ali1688:{ak_id}", True)
    deleted = account_client.delete(f"/v1/accounts/ali1688:{ak_id}")
    assert deleted.status_code == 200
    assert get_ak() == (None, None)
