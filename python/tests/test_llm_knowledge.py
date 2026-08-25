"""LLM / 知识库 / 配置层单元测试。"""

from __future__ import annotations

import unittest

from config.settings import AiSettings
from knowledge import ItemKnowledge, build_item_context
from llm.factory import create_provider, normalize_provider_type
from services.price import compare_prices
from services.product import match_products, normalize_products


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

    def test_create_openai_provider(self) -> None:
        dummy = "k"
        settings = AiSettings(
            api_key=dummy,
            base_url="https://api.deepseek.com/v1",
            model_name="m",
        ).to_provider_settings()
        provider = create_provider(settings)
        self.assertEqual(provider.kind, "openai_compatible")
        self.assertTrue(provider.supports_tools)


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
