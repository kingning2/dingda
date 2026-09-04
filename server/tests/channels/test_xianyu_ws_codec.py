"""闲鱼 WS 编解码单测（不连真实 WebSocket）。"""

from __future__ import annotations

import base64
import json

from src.channels.xianyu.ws import (
    build_ack,
    extract_incoming_text,
    extract_meta_event,
    extract_push_message,
)


def _wrap(data_str: str) -> dict:
    return {
        "headers": {"mid": "m1", "sid": "s1"},
        "lwp": "/s/para",
        "body": {"syncPushPackage": {"data": [{"data": data_str}]}},
    }


def test_extract_push_plain_json() -> None:
    payload = {"chatType": 1, "sessionId": "999"}
    assert extract_push_message(_wrap(json.dumps(payload))) == payload


def test_extract_push_base64_json() -> None:
    payload = {
        "operation": {"content": {"contentType": 1, "text": {"text": "你好"}}},
        "sessionId": "88888",
    }
    b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    assert extract_push_message(_wrap(b64)) == payload


def test_extract_push_missing_path() -> None:
    assert extract_push_message({"headers": {}, "body": {}}) is None


def test_incoming_text_new_format() -> None:
    decoded = {
        "sessionId": "12345",
        "operation": {
            "content": {
                "contentType": 1,
                "text": {"text": "可以砍价吗"},
                "reminder": {
                    "reminderTitle": "小号昵称",
                    "reminderContent": "可以砍价吗",
                },
            },
            "senderInfo": {"senderUserId": "test-user"},
        },
    }
    got = extract_incoming_text(decoded)
    assert got == {
        "event": "message",
        "cid": "12345",
        "content_type": 1,
        "send_user_id": "test-user",
        "send_user_name": "小号昵称",
        "send_message": "可以砍价吗",
    }


def test_incoming_text_custom_wrapped() -> None:
    inner = {"contentType": 1, "text": {"text": "hi"}}
    custom_b64 = base64.b64encode(json.dumps(inner).encode()).decode()
    decoded = {
        "sessionId": "999",
        "operation": {
            "content": {"contentType": 101, "custom": {"type": 1, "data": custom_b64}},
            "senderInfo": {"senderUserId": "u1"},
        },
    }
    got = extract_incoming_text(decoded)
    assert got is not None
    assert got["send_message"] == "hi"
    assert got["content_type"] == 101


def test_meta_new_msg() -> None:
    got = extract_meta_event({"1": "cid1@goofish", "2": 1, "3": "mid", "4": "ts"})
    assert got == {"event": "new_msg", "cid": "cid1", "msg_id": "mid", "ts": "ts"}


def test_build_ack() -> None:
    ack = build_ack({"headers": {"mid": "m", "sid": "s", "app-key": "k"}})
    assert ack["code"] == 200
    assert ack["headers"]["mid"] == "m"
    assert ack["headers"]["app-key"] == "k"
