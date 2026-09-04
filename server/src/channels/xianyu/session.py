"""闲鱼 HTTP Session：由账号 cookie 构造 requests 会话。

职责：
    解析 cookie header → requests.Session + unb / device_id；
    device_id 按 unb 缓存在产品数据目录，避免 IM/token 不一致。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：本包 mtop、message、media、token 及 crawler 详情拉取
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from src.channels.cookie_header import parse_cookie_header
from src.channels.xianyu.sign import generate_device_id
from src.shared.errors import AppError

logger = logging.getLogger("dingda.channel.xianyu.session")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

_REQUIRED = ("unb", "_m_h5_tk")


@dataclass
class Session:
    """闲鱼已登录 HTTP 会话。"""

    http: requests.Session
    unb: str
    tracknick: str
    device_id: str

    @classmethod
    def from_cookie_header(cls, cookie: str) -> Session:
        """用账号 cookie 字符串构造 Session。"""
        cookies = parse_cookie_header(cookie)
        missing = [key for key in _REQUIRED if not cookies.get(key)]
        if missing:
            raise AppError(
                "account.session_expired",
                f"cookie 缺字段: {', '.join(missing)}",
                status_code=401,
            )
        http = requests.Session()
        http.cookies.update(cookies)
        return cls(
            http=http,
            unb=cookies["unb"],
            tracknick=cookies.get("tracknick", ""),
            device_id=_load_or_mint_device_id(cookies["unb"]),
        )

    @property
    def h5_token(self) -> str:
        raw = self.http.cookies.get("_m_h5_tk", "")
        return raw.split("_")[0] if raw else ""

    def sync_cookies(self, cookies: dict[str, str]) -> None:
        """用新 cookie 覆盖 http 会话（浏览器续期后回写）。"""
        self.http.cookies.clear()
        self.http.cookies.update(cookies)


def _device_cache_path() -> Path:
    from src.infrastructure.db.session import data_dir

    return data_dir() / "xianyu" / "device.json"


def _load_or_mint_device_id(unb: str) -> str:
    path = _device_cache_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("unb") == unb and raw.get("device_id"):
                return str(raw["device_id"])
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("读取 device_id 缓存失败: %s", exc)
    device_id = generate_device_id(unb)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"unb": unb, "device_id": device_id}), encoding="utf-8")
    except OSError as exc:
        logger.debug("写入 device_id 缓存失败: %s", exc)
    return device_id
