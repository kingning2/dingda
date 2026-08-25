"""历史消息解析单元测试。"""

from __future__ import annotations

import base64
import json
import unittest

from crawlers.xianyu.ws.frames import list_user_messages_frame
from crawlers.xianyu.ws.history import decode_history_content, parse_history_message


class TestHistoryParse(unittest.TestCase):
    def test_list_user_messages_frame(self) -> None:
        frame = list_user_messages_frame("cid1", 9007199254740991, 20)
        self.assertEqual(frame["lwp"], "/r/MessageManager/listUserMessages")
        self.assertEqual(frame["body"][0], "cid1@goofish")
        self.assertEqual(frame["body"][2], 9007199254740991)
        self.assertEqual(frame["body"][3], 20)

    def test_decode_nested_text(self) -> None:
        payload = {"text": {"text": "你好"}}
        encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode(
            "ascii",
        )
        self.assertEqual(decode_history_content(encoded), "你好")

    def test_parse_history_message(self) -> None:
        payload = {"text": {"text": "在吗"}}
        encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode(
            "ascii",
        )
        model = {
            "message": {
                "extension": {"senderUserId": "u1", "reminderTitle": "买家"},
                "content": {"custom": {"data": encoded}},
                "createTime": 123,
            },
        }
        parsed = parse_history_message(model)
        assert parsed is not None
        self.assertEqual(parsed["sender_user_id"], "u1")
        self.assertEqual(parsed["content"], "在吗")
        self.assertEqual(parsed["created_at_ms"], 123)


if __name__ == "__main__":
    unittest.main()
