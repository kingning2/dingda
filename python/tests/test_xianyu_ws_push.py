"""闲鱼 WSS push 解析测试 — 对齐 Rust push.rs。

校验 syncPushPackage 解码、会话聚合与入站文本提取。"""

from __future__ import annotations

import base64
import json
import unittest

from crawlers.xianyu.ws.push import (
    decode_push_payload,
    extract_incoming_text,
    parse_sync_push_package,
)


class TestXianyuWsPush(unittest.TestCase):
    def test_decode_plain_and_base64(self) -> None:
        plain = '{"sessionId":"111@goofish"}'
        self.assertEqual(decode_push_payload(plain)["sessionId"], "111@goofish")
        b64 = base64.b64encode(plain.encode()).decode()
        self.assertEqual(decode_push_payload(b64)["sessionId"], "111@goofish")

    def test_extract_session(self) -> None:
        payload = {
            "sessionId": "60585751957@goofish",
            "operation": {
                "sessionInfo": {
                    "extensions": {
                        "itemId": "item-9",
                        "itemTitle": "二手手机",
                        "extUserId": "seller-self-id",
                    },
                },
            },
        }
        frame = {"body": {"syncPushPackage": {"data": [{"data": json.dumps(payload)}]}}}
        batch = parse_sync_push_package(frame)
        self.assertEqual(len(batch.sessions), 1)
        self.assertEqual(batch.sessions[0].cid, "60585751957")
        self.assertEqual(batch.sessions[0].item_id, "item-9")

    def test_extract_text_message(self) -> None:
        payload = {
            "sessionId": "cid1@goofish",
            "operation": {
                "content": {
                    "contentType": 1,
                    "text": {"text": "还在吗"},
                    "reminder": {
                        "reminderTitle": "买家",
                        "senderUserId": "peer-42",
                        "reminderContent": "还在吗",
                    },
                },
                "senderInfo": {"senderUserId": "peer-42"},
                "sessionInfo": {"extensions": {"itemId": "item-1"}},
            },
        }
        msg = extract_incoming_text(payload)
        assert msg is not None
        self.assertEqual(msg.cid, "cid1")
        self.assertEqual(msg.peer_id, "peer-42")
        self.assertEqual(msg.content, "还在吗")


if __name__ == "__main__":
    unittest.main()
