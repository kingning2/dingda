"""ai_probe handlers — 空 key / URL 归一化（不打真实网络）。"""

from __future__ import annotations

import unittest
from unittest import mock

from dingda_sidecar.runtime.handlers import ai_probe
from dingda_sidecar.runtime.ipc import HANDLERS, ROUTES


class AiProbeTests(unittest.TestCase):
    def test_routes_registered(self) -> None:
        self.assertEqual(ROUTES["/v1/ai/probe_key"], ("POST", "handle_ai_probe_key"))
        self.assertEqual(ROUTES["/v1/ai/account_balance"], ("POST", "handle_ai_account_balance"))
        self.assertEqual(
            ROUTES["/v1/ai/providers_catalog"],
            ("POST", "handle_ai_providers_catalog"),
        )
        self.assertEqual(ROUTES["/v1/ai/list_models"], ("POST", "handle_ai_list_models"))
        self.assertIn("handle_ai_probe_key", HANDLERS)
        self.assertIn("handle_ai_account_balance", HANDLERS)
        self.assertIn("handle_ai_providers_catalog", HANDLERS)
        self.assertIn("handle_ai_list_models", HANDLERS)

    def test_providers_catalog_from_registry(self) -> None:
        result = ai_probe.handle_ai_providers_catalog(None, trace_id="t")
        providers = result["providers"]
        self.assertIsInstance(providers, list)
        self.assertGreaterEqual(len(providers), 1)
        ids = {item["id"] for item in providers}
        self.assertIn("deepseek", ids)
        self.assertIn("anthropic", ids)
        self.assertIn("gemini", ids)
        self.assertIn("dashscope_app", ids)

    def test_list_models_empty_key_cloud(self) -> None:
        result = ai_probe.handle_ai_list_models(
            {"base_url": "https://api.openai.com/v1", "api_key": ""},
            trace_id="t",
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["models"], [])

    def test_list_models_parse_success(self) -> None:
        body = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]}
        with mock.patch.object(ai_probe, "_http_get_json", return_value=(200, body)):
            result = ai_probe.handle_ai_list_models(
                {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-test",
                },
                trace_id="t",
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["models"], ["gpt-4o", "gpt-4o-mini"])

    def test_probe_key_empty(self) -> None:
        result = ai_probe.handle_ai_probe_key(
            {"base_url": "https://api.openai.com", "api_key": "  "},
            trace_id="t",
        )
        self.assertFalse(result["ok"])
        self.assertIn("空", result["message"])

    def test_account_balance_empty(self) -> None:
        result = ai_probe.handle_ai_account_balance(
            {"base_url": "https://api.deepseek.com", "api_key": ""},
            trace_id="t",
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["balances"], [])

    def test_openai_compatible_root(self) -> None:
        self.assertEqual(
            ai_probe._openai_compatible_root("https://api.openai.com"),
            "https://api.openai.com/v1",
        )
        self.assertEqual(
            ai_probe._openai_compatible_root("https://api.openai.com/v1"),
            "https://api.openai.com/v1",
        )

    def test_probe_key_models_success(self) -> None:
        with mock.patch.object(ai_probe, "_http_get_json", return_value=(200, {"data": []})):
            result = ai_probe.handle_ai_probe_key(
                {
                    "base_url": "https://api.openai.com",
                    "api_key": "sk-test",
                    "kind": "openai",
                },
                trace_id="t",
            )
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
