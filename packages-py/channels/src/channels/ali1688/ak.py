"""1688 Access Key 读写。

职责：
    从环境变量或本地配置解析 AK ID/Secret；支持写入、探活与清除。
    供 sign / client 签名与账号域探活/删除调用，不负责 HTTP。

设计说明：
    - 优先 ``ALI_1688_AK``，其次 ``~/.dingda/v2/ali1688/ak.json``
    - AK 格式与 1688 Skill 一致：base64url，前 32 为 Secret，其余为 ID
    - 探活只比对账户存的 AK 是否仍在；删除账户时清对应本地文件

使用示例：
    ak_id, secret = get_ak()
    save_ak(raw)
    ok = probe(stored_raw)
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

from infrastructure.db.session import data_dir

logger = logging.getLogger("dingda.channel.ali1688.ak")

ENV_AK = "ALI_1688_AK"


def _ak_path() -> Path:
    """AK 配置文件路径。"""
    return data_dir() / "ali1688" / "ak.json"


def extract_ak_keys(raw_ak: str) -> tuple[str | None, str | None]:
    """从原始 AK 字符串拆出 (ak_id, ak_secret)。"""
    if not raw_ak:
        return None, None

    try:
        padded = raw_ak + "=" * (-len(raw_ak) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        secret = decoded[:32]
        ak_id = decoded[32:]
        if ak_id:
            return ak_id, secret
    except Exception:
        pass

    if len(raw_ak) > 32:
        return raw_ak[32:], raw_ak[:32]
    return None, None


def _raw_from_file() -> str | None:
    """从本地配置文件读原始 AK。"""
    path = _ak_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ak = data.get("ak")
    return ak if isinstance(ak, str) and ak else None


def get_ak() -> tuple[str | None, str | None]:
    """读取 AK：环境变量优先，配置文件兜底。"""
    raw = raw_ak()
    if not raw:
        return None, None
    return extract_ak_keys(raw)


def raw_ak() -> str | None:
    """原始 AK 字符串（环境变量优先）。"""
    env = os.environ.get(ENV_AK)
    if isinstance(env, str) and env.strip():
        return env.strip()
    return _raw_from_file()


def ak_configured() -> bool:
    """是否已配置可用 AK。"""
    ak_id, secret = get_ak()
    return bool(ak_id and secret)


def probe(stored_raw: str) -> bool:
    """该账户的 AK 是否仍存在（与本地/环境变量中的 AK 对得上）。"""
    stored = (stored_raw or "").strip()
    current = raw_ak()
    if not stored or not current:
        return False
    if stored == current:
        return True
    stored_id, _ = extract_ak_keys(stored)
    current_id, _ = extract_ak_keys(current)
    return bool(stored_id and current_id and stored_id == current_id)


def save_ak(raw: str) -> None:
    """持久化原始 AK 到本地配置。"""
    ak_id, secret = extract_ak_keys(raw)
    if not ak_id or not secret:
        raise ValueError("AK 格式不正确")
    path = _ak_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ak": raw}, ensure_ascii=False), encoding="utf-8")
    logger.info("AK 已保存 path=%s", path)


def clear_ak() -> None:
    """删除本地 AK 配置（不影响环境变量）。"""
    path = _ak_path()
    if path.exists():
        path.unlink()
        logger.info("AK 配置已清除 path=%s", path)


def clear_account_ak(stored_raw: str) -> None:
    """删除该账户对应的本地 AK 文件（环境变量不改）。"""
    stored = (stored_raw or "").strip()
    file_raw = _raw_from_file()
    if not file_raw:
        return
    if stored and (stored == file_raw.strip()):
        clear_ak()
        return
    stored_id, _ = extract_ak_keys(stored)
    file_id, _ = extract_ak_keys(file_raw)
    if stored_id and file_id and stored_id == file_id:
        clear_ak()
