"""闲鱼 Playwright 配置与会话辅助。"""

from __future__ import annotations

import logging
import os
from typing import Any

from crawlers.core.browser.base import BrowserPlatform
from crawlers.core.playwright_common import CHROME_DESKTOP_UA, inject_init_script
from crawlers.xianyu.browser.session import (
    looks_blocked,
    prepare_cookies,
    profile_dir,
    resolve_headless,
)

# 闲鱼 / 阿里 Baxia 风控：注入到每个页面的反检测脚本。
_ANTI_DETECT_SCRIPT = r"""
(() => {
  try {
    const NAV = navigator;
    const DEF = (target, name, value) => {
      try {
        Object.defineProperty(target, name, { get: () => value, configurable: true });
      } catch (e) {}
    };
    DEF(Navigator.prototype, 'platform', 'Win32');
    DEF(NAV, 'platform', 'Win32');
    DEF(NAV, 'vendor', 'Google Inc.');
    const ua = NAV.userAgent || '';
    if (ua) DEF(NAV, 'appVersion', ua.replace(/^Mozilla\//, ''));
    DEF(NAV, 'hardwareConcurrency', 8);
    DEF(NAV, 'deviceMemory', 8);
    const ver = (ua.match(/Chrome\/([\d]+)/) || [, '146'])[1];
    const brands = [
      { brand: 'Google Chrome', version: ver },
      { brand: 'Chromium', version: ver },
      { brand: 'Not.A/Brand', version: '8' },
    ];
    DEF(NAV, 'userAgentData', {
      brands,
      mobile: false,
      platform: 'Windows',
      getHighEntropyValues: (hints) => Promise.resolve({
        architecture: 'x86', bitness: '64', brands,
        fullVersionList: brands, mobile: false, model: '',
        platform: 'Windows', platformVersion: '15.0.0',
        uaFullVersion: ver, wow64: false,
      }),
      toJSON: () => ({ brands, mobile: false, platform: 'Windows' }),
    });
    const wrapWebGL = (Ctx) => {
      if (!Ctx) return;
      const orig = Ctx.prototype.getParameter;
      Ctx.prototype.getParameter = function (param) {
        if (param === 0x9245) return 'Google Inc. (NVIDIA)';
        if (param === 0x9246) {
          return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)';
        }
        return orig.call(this, param);
      };
    };
    wrapWebGL(WebGLRenderingContext);
    if (typeof WebGL2RenderingContext !== 'undefined') wrapWebGL(WebGL2RenderingContext);
    const origData = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function (...args) {
      const ctx = this.getContext('2d');
      if (ctx) {
        try {
          const w = this.width, h = this.height;
          if (w > 0 && h > 0) {
            const img = ctx.getImageData(0, 0, w, h);
            for (let i = 0; i < img.data.length; i += 4) {
              if (Math.random() < 0.03) {
                img.data[i] = (img.data[i] + (Math.random() < 0.5 ? -1 : 1)) & 0xff;
              }
            }
            ctx.putImageData(img, 0, 0);
          }
        } catch (e) {}
      }
      return origData.apply(this, args);
    };
    for (const key of Object.keys(window)) {
      if (key.startsWith('cdc_')) { try { delete window[key]; } catch (e) {} }
    }
  } catch (e) {}
})();
"""


class XianyuBrowser(BrowserPlatform):
    """闲鱼浏览器启动配置。"""

    @property
    def platform_id(self) -> str:
        return "xianyu"

    def resolve_user_agent(self) -> str:
        configured = os.getenv("DINGDA_XIANYU_LOGIN_USER_AGENT", "").strip()
        return configured or CHROME_DESKTOP_UA

    def resolve_proxy(self) -> dict[str, str] | None:
        server = os.getenv("DINGDA_XIANYU_PROXY_SERVER", "").strip()
        username = os.getenv("DINGDA_XIANYU_PROXY_USERNAME", "").strip()
        password = os.getenv("DINGDA_XIANYU_PROXY_PASSWORD", "").strip()
        if not server:
            return None
        proxy: dict[str, str] = {"server": server}
        if username:
            proxy["username"] = username
        if password:
            proxy["password"] = password
        return proxy

    async def apply_anti_detect(self, context: Any, logger: logging.Logger) -> None:
        await inject_init_script(context, _ANTI_DETECT_SCRIPT, logger)


__all__ = [
    "XianyuBrowser",
    "looks_blocked",
    "prepare_cookies",
    "profile_dir",
    "resolve_headless",
]
