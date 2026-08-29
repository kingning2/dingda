"""Cookie 加密存储。Fernet (AES-128-CBC + HMAC-SHA256) + PBKDF2 机器密钥。

密钥从 hostname + username 派生，无需用户输入密码。
同一机器每次派生相同密钥，跨机器密钥不同（cookie 文件不可迁移）。
"""
from __future__ import annotations

import getpass
import hashlib
import json
import platform

from cryptography.fernet import Fernet, InvalidToken

_SALT = b"goofish-cli-cookie-enc-v1"
_ITERATIONS = 480_000


def _machine_key() -> bytes:
    raw = f"{platform.node()}:{getpass.getuser()}:goofish-cli".encode()
    dk = hashlib.pbkdf2_hmac("sha256", raw, _SALT, _ITERATIONS)
    return __import__("base64").urlsafe_b64encode(dk)


def encrypt_cookies(cookies: dict[str, str]) -> bytes:
    payload = json.dumps(cookies, ensure_ascii=False).encode()
    return Fernet(_machine_key()).encrypt(payload)


def decrypt_cookies(data: bytes) -> dict[str, str]:
    try:
        plain = Fernet(_machine_key()).decrypt(data)
    except InvalidToken as e:
        raise ValueError("cookie 解密失败（可能在其他机器上加密的）") from e
    return json.loads(plain)
