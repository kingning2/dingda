"""页面 localStorage 读写（登录落库 / 预览注入）。

职责：
    从 Playwright page 同步读出 localStorage；失败返回空 dict，不打断登录。

使用示例：
    data = read_local_storage(page)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("dingda.channels.storage")

_READ_JS = """() => {
  const out = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key != null) out[key] = String(localStorage.getItem(key) ?? "");
    }
  } catch (e) {}
  return out;
}"""


def read_local_storage(page: Any) -> dict[str, str]:
    """同步读取页内 localStorage；异常时返回空。"""
    if page is None:
        return {}
    try:
        raw = page.evaluate(_READ_JS)
    except Exception:  # noqa: BLE001
        logger.debug("read localStorage failed", exc_info=True)
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        out[name] = "" if value is None else str(value)
    logger.info("localStorage keys=%s", len(out))
    return out
