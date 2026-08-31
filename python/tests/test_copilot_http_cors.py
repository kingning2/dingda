"""副驾直连 HTTP — CORS 预检。"""

from __future__ import annotations

import unittest
from http.client import HTTPConnection

from dingda_sidecar.runtime.server import COPILOT_SSE_PATH, start_copilot_http_server


class TestCopilotHttpCors(unittest.TestCase):
    def test_options_preflight_allows_cross_origin_post(self) -> None:
        port = start_copilot_http_server()
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "OPTIONS",
            COPILOT_SSE_PATH,
            headers={
                "Origin": "http://localhost:1420",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type, accept",
            },
        )
        response = conn.getresponse()
        self.assertEqual(response.status, 204)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "http://localhost:1420")
        self.assertIn("POST", response.getheader("Access-Control-Allow-Methods") or "")
        conn.close()


if __name__ == "__main__":
    unittest.main()
