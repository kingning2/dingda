"""WebSocket LWP 帧构造 — 对齐 Rust ``message/frames.rs``。

生成注册、心跳、ACK、发消息与历史拉取等帧，以及 mid/uuid/cid 辅助函数。"""

from __future__ import annotations

import base64
import json
import random
from typing import Any

from crawlers.xianyu.ws.constants import REG_APP_KEY
from crawlers.xianyu.ws.cookies import now_ms


def generate_mid() -> str:
    return f"{random.randint(0, 999)}{now_ms()} 0"


def generate_uuid() -> str:
    return f"-{now_ms()}1"


def register_frame(device_id: str, token: str) -> dict[str, Any]:
    return {
        "lwp": "/reg",
        "headers": {
            "cache-header": "app-key token ua wv",
            "app-key": REG_APP_KEY,
            "token": token,
            "ua": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 "
                "DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) DingWeb/2.1.5"
            ),
            "dt": "j",
            "wv": "im:3,au:3,sy:6",
            "sync": "0,0;0;0;",
            "did": device_id,
            "mid": generate_mid(),
        },
    }


def sync_ack_frame(*, pts: int | None = None) -> dict[str, Any]:
    current_ms = now_ms()
    return {
        "lwp": "/r/SyncStatus/ackDiff",
        "headers": {"mid": generate_mid()},
        "body": [
            {
                "pipeline": "sync",
                "tooLong2Tag": "PNM,1",
                "channel": "sync",
                "topic": "sync",
                "highPts": 0,
                "pts": pts if pts is not None else 0,
                "seq": 0,
                "timestamp": current_ms,
            },
        ],
    }


def heartbeat_frame() -> dict[str, Any]:
    return {"lwp": "/!", "headers": {"mid": generate_mid()}}


def ack_frame(headers: dict[str, Any]) -> dict[str, Any]:
    out_headers: dict[str, Any] = {
        "mid": headers.get("mid") or generate_mid(),
        "sid": headers.get("sid") or "",
    }
    for key in ("app-key", "ua", "dt"):
        if key in headers:
            out_headers[key] = headers[key]
    return {"code": 200, "headers": out_headers}


def normalize_peer(peer_id: str, domain: str = "goofish") -> str:
    return peer_id if "@" in peer_id else f"{peer_id}@{domain}"


def send_message_frame(cid: str, to_id: str, my_id: str, text: str) -> dict[str, Any]:
    cid_norm = normalize_peer(cid)
    to_norm = normalize_peer(to_id)
    mine = normalize_peer(my_id)
    content_json = json.dumps({"contentType": 1, "text": {"text": text}}, ensure_ascii=False)
    content_b64 = base64.b64encode(content_json.encode("utf-8")).decode("ascii")
    return {
        "lwp": "/r/MessageSend/sendByReceiverScope",
        "headers": {"mid": generate_mid()},
        "body": [
            {
                "uuid": generate_uuid(),
                "cid": cid_norm,
                "conversationType": 1,
                "content": {
                    "contentType": 101,
                    "custom": {"type": 1, "data": content_b64},
                },
                "redPointPolicy": 0,
                "extension": {"extJson": "{}"},
                "ctx": {"appVersion": "1.0", "platform": "web"},
                "mtags": {},
                "msgReadStatusSetting": 1,
            },
            {"actualReceivers": [to_norm, mine]},
        ],
    }


def list_user_messages_frame(cid: str, cursor: int, limit: int) -> dict[str, Any]:
    return {
        "lwp": "/r/MessageManager/listUserMessages",
        "headers": {"mid": generate_mid()},
        "body": [normalize_peer(cid), False, cursor, limit, False],
    }


def extract_cid(raw: str) -> str:
    return raw.split("@", 1)[0]
