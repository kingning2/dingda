"""Cookie 加密模块测试。"""
from __future__ import annotations

from goofish_cli.core.crypto import decrypt_cookies, encrypt_cookies


def test_round_trip():
    cookies = {"unb": "U123", "_m_h5_tk": "T_xxx_1", "tracknick": "test"}
    encrypted = encrypt_cookies(cookies)
    decrypted = decrypt_cookies(encrypted)
    assert decrypted == cookies


def test_different_ciphertext_each_time():
    """相同明文每次加密应产生不同密文（随机 IV）。"""
    cookies = {"unb": "U1"}
    a = encrypt_cookies(cookies)
    b = encrypt_cookies(cookies)
    assert a != b
    # 但都能正确解密
    assert decrypt_cookies(a) == decrypt_cookies(b) == cookies


def test_tampered_ciphertext_fails():
    """篡改密文应解密失败。"""
    encrypted = encrypt_cookies({"k": "v"})
    tampered = encrypted[:-4] + b"xxxx"
    try:
        decrypt_cookies(tampered)
        raise AssertionError("应该抛异常")
    except ValueError:
        pass


def test_empty_dict():
    assert decrypt_cookies(encrypt_cookies({})) == {}


def test_unicode_values():
    cookies = {"tracknick": "用户昵称"}
    assert decrypt_cookies(encrypt_cookies(cookies)) == cookies
