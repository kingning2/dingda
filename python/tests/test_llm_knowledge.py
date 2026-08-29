"""LLM / 知识库 / 配置层单元测试。

校验 Provider 类型归一、知识服务与比价/商品服务纯函数。"""

from __future__ import annotations

import unittest

from dingda_sidecar.agent.graph.model import create_chat_model
from dingda_sidecar.agent.knowledge import ItemKnowledge, build_item_context
from dingda_sidecar.agent.llm.factory import normalize_provider_type
from dingda_sidecar.config.settings import AiSettings
from dingda_sidecar.services.price import compare_prices
from dingda_sidecar.services.product import match_products, normalize_products


class TestLlmFactory(unittest.TestCase):
    def test_normalize_deepseek(self) -> None:
        self.assertEqual(
            normalize_provider_type("deepseek", "", "deepseek-chat"),
            "openai_compatible",
        )

    def test_normalize_claude_by_url(self) -> None:
        self.assertEqual(
            normalize_provider_type("", "https://api.anthropic.com", ""),
            "anthropic",
        )

    def test_create_chat_model_builtin(self) -> None:
        try:
            import langchain_openai  # noqa: F401
        except ImportError:
            self.skipTest("langchain_openai not installed")
        settings = AiSettings(
            api_key=("k"),
            base_url="https://api.deepseek.com/v1",
            model_name="m",
        )
        model = create_chat_model(settings)
        self.assertEqual(type(model).__name__, "ChatOpenAI")


class TestKnowledge(unittest.TestCase):
    def test_json_desc(self) -> None:
        item = ItemKnowledge(title="二手电脑", price=100.0, desc='{"description":"九成新"}')
        ctx = build_item_context(item)
        self.assertIn("九成新", ctx)
        self.assertIn("100", ctx)


class TestServices(unittest.TestCase):
    def test_price_compare(self) -> None:
        norm = normalize_products(
            [{"title": "iPhone 15", "price": "5000"}],
            [{"title": "iPhone 15", "price": "4800"}],
        )
        matches = match_products(norm)
        comps = compare_prices(matches)
        self.assertEqual(comps[0]["spread"], 200.0)


if __name__ == "__main__":
    unittest.main()
