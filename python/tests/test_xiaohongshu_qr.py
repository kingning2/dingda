"""小红书扫码渠道轻量测试 — 验证渠道工厂与平台配置可解析。

扫码全流程依赖真实浏览器，不做启动；这里只锁定渠道接线正确。"""

from __future__ import annotations

import unittest

from dingda_sidecar.crawlers.core.platform_config import get_platform_config
from dingda_sidecar.crawlers.factory import create_channel


class TestXiaohongshuQrChannel(unittest.TestCase):
    def test_channel_qrcode_platform(self) -> None:
        channel = create_channel("xiaohongshu")
        qr = channel.qrcode()
        self.assertEqual(qr.platform, "xiaohongshu")
        self.assertEqual(channel.browser().platform_id, "xiaohongshu")

    def test_platform_config(self) -> None:
        cfg = get_platform_config("xiaohongshu")
        self.assertEqual(cfg.login_cookie_name, "web_session")
        self.assertEqual(cfg.cookie_domain_keyword, "xiaohongshu.com")
        self.assertTrue(cfg.qr_selectors)


if __name__ == "__main__":
    unittest.main()
