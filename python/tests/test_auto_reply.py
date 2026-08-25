"""auto_reply / LangGraph 买家回复单元测试。

覆盖意图路由与 buyer_reply 图在守卫/生成路径上的行为。"""

from __future__ import annotations

import unittest

from agents.intent import Intent, route_intent
from config.settings import AiSettings
from graph.core.model import BARGAIN_LIMIT_REPLY
from graph.workflows.buyer_reply import run_buyer_reply


class TestIntent(unittest.TestCase):
    def test_price_intent(self) -> None:
        self.assertEqual(route_intent("能便宜点吗"), Intent.PRICE)

    def test_no_reply(self) -> None:
        self.assertEqual(route_intent("谢谢"), Intent.NO_REPLY)


class TestBuyerReply(unittest.TestCase):
    def test_skips_when_ai_disabled(self) -> None:
        settings = AiSettings(ai_enabled=False)
        reply = run_buyer_reply(settings, {"content": "在吗"})
        self.assertIsNone(reply)

    def test_bargain_limit_without_llm(self) -> None:
        settings = AiSettings(
            ai_enabled=True,
            max_bargain_rounds=1,
        )
        reply = run_buyer_reply(
            settings,
            {"content": "便宜点", "bargain_count": 2},
        )
        self.assertEqual(reply, BARGAIN_LIMIT_REPLY)


if __name__ == "__main__":
    unittest.main()
