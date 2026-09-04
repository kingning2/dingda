"""1688 AK / 签名单测。"""

from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path

from src.channels.ali1688.ak import (
    clear_account_ak,
    clear_ak,
    extract_ak_keys,
    get_ak,
    probe,
    save_ak,
)
from src.channels.ali1688.sign import CLIENT_VERSION, build_signature, sign_string_for_test


def test_extract_ak_keys_base64url() -> None:
    secret = "a" * 32
    ak_id = "my-ak-id-001"
    raw = base64.urlsafe_b64encode(f"{secret}{ak_id}".encode()).decode().rstrip("=")
    got_id, got_secret = extract_ak_keys(raw)
    assert got_id == ak_id
    assert got_secret == secret


def test_extract_ak_keys_raw_concat() -> None:
    secret = "b" * 32
    ak_id = "plain-id"
    got_id, got_secret = extract_ak_keys(secret + ak_id)
    assert got_id == ak_id
    assert got_secret == secret


def test_save_and_get_ak(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "src.channels.ali1688.ak.data_dir",
        lambda: tmp_path,
    )
    monkeypatch.delenv("ALI_1688_AK", raising=False)
    secret = "c" * 32
    ak_id = "stored-id"
    raw = base64.urlsafe_b64encode(f"{secret}{ak_id}".encode()).decode().rstrip("=")
    save_ak(raw)
    got_id, got_secret = get_ak()
    assert got_id == ak_id
    assert got_secret == secret
    clear_ak()
    assert get_ak() == (None, None)


def test_probe_and_clear_account_ak(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.channels.ali1688.ak.data_dir", lambda: tmp_path)
    monkeypatch.delenv("ALI_1688_AK", raising=False)
    secret = "d" * 32
    ak_id = "probe-id"
    raw = base64.urlsafe_b64encode(f"{secret}{ak_id}".encode()).decode().rstrip("=")
    save_ak(raw)
    assert probe(raw) is True
    assert probe("not-this-ak") is False
    clear_account_ak(raw)
    assert probe(raw) is False
    assert get_ak() == (None, None)


def test_build_signature_deterministic_string() -> None:
    body = '{"query":"卫衣"}'
    uri = "/api/alibaba.1688.find.product/1.0.0/dingda"
    string_to_sign = sign_string_for_test(
        "POST",
        uri,
        body,
        ak_id="id1",
        ak_secret="s" * 32,
        timestamp="1700000000",
        nonce="abc12345",
    )
    assert string_to_sign.startswith("POST\n")
    assert "x-csk-ak:id1\n" in string_to_sign
    assert string_to_sign.endswith(uri)

    headers = build_signature(
        "POST",
        uri,
        body,
        ak_id="id1",
        ak_secret="s" * 32,
    )
    assert headers["Content-Type"] == "application/json"
    assert headers["x-csk-ak"] == "id1"
    assert headers["x-csk-version"] == CLIENT_VERSION
    assert "x-csk-sign" in headers

    # 用同一算法复核：签名头应是 HMAC 的 base64
    content_md5 = base64.b64encode(hashlib.md5(body.encode()).digest()).decode()
    assert headers["x-csk-content-md5"] == content_md5
    # 仅验证签名可解码为 32 字节
    raw_sig = base64.b64decode(headers["x-csk-sign"])
    assert len(raw_sig) == 32
    # 与临时重算对照（使用 headers 内 time/nonce）
    csk = {
        "x-csk-ak": headers["x-csk-ak"],
        "x-csk-time": headers["x-csk-time"],
        "x-csk-nonce": headers["x-csk-nonce"],
        "x-csk-content-md5": headers["x-csk-content-md5"],
        "x-csk-version": headers["x-csk-version"],
    }
    canon = "".join(f"{k.lower()}:{csk[k].strip()}\n" for k in sorted(csk))
    expected = hmac.new(
        ("s" * 32).encode(),
        (
            f"POST\n{content_md5}\napplication/json\n{headers['x-csk-time']}\n{canon}{uri}"
        ).encode(),
        hashlib.sha256,
    ).digest()
    assert raw_sig == expected
