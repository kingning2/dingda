"""探针：用本地页面验证闲鱼的「就绪判据 JS」是否真的判得对。

职责：
    排障 / 回归用。``LIST_READY_JS`` / ``DETAIL_READY_JS`` 是纯 JS 字符串，Python
    不做语法检查——写错了只有真机跑才暴露，而症状是「白等满 8 秒」，极难归因。
    这里用本地 HTML 模拟「有卡片 / 被风控 / 需登录 / 空结果 / 空白」几种状态，
    真实执行判据（连 ``extract.json`` 的选择器一起验），**不碰任何平台**。

使用示例：
    python -m api.scripts.probe_xianyu_ready_js
"""

from __future__ import annotations

import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from browser.registry import create_browser
from contracts.browser_port import LaunchOptions
from crawler.sources.xianyu.extractor import (
    DETAIL_READY_JS,
    LIST_READY_JS,
    detail_ready_arg,
    list_ready_arg,
)

# 各页面只放「判据该不该命中」的最小结构
_PAGES: dict[str, str] = {
    # 有卡片 → 就绪
    "/list.html": """<!doctype html><html><body>
<a href="/item?id=123">商品 A</a>
</body></html>""",
    # 被风控 → 必须也算「就绪」，否则会白等满超时把「被拦」拖成「抽取失败」
    "/blocked.html": """<!doctype html><html><body>
<div>请完成验证码</div>
</body></html>""",
    # 需登录 → 同上
    "/auth.html": """<!doctype html><html><body>
<div>请先登录后查看</div>
</body></html>""",
    # 空结果 → 也算就绪（有结论了）
    "/empty.html": """<!doctype html><html><body>
<div>暂无相关宝贝</div>
</body></html>""",
    # 什么都没有 → 不该就绪
    "/blank.html": """<!doctype html><html><body>
<div>普通页面</div>
</body></html>""",
    # 详情：信息块 + 价格 + 够长的描述 → 就绪
    "/detail.html": """<!doctype html><html><body>
<div class="item-main-container">
  <div class="item-main-info">
    <div class="price">¥199</div>
    <div class="desc">这是一段足够长的商品描述文案用于判据</div>
  </div>
</div>
</body></html>""",
    # 详情：只有价格、文案太短 → 还不算渲染完
    "/detail-thin.html": """<!doctype html><html><body>
<div class="item-main-info"><div class="price">¥1</div></div>
</body></html>""",
    # 详情：风控页 → 立刻算就绪
    "/detail-blocked.html": """<!doctype html><html><body>
<div>安全验证</div>
</body></html>""",
}

# 期望值：路径 → 判据是否应命中
_LIST_CASES: list[tuple[str, bool]] = [
    ("/list.html", True),
    ("/blocked.html", True),
    ("/auth.html", True),
    ("/empty.html", True),
    ("/blank.html", False),
]

_DETAIL_CASES: list[tuple[str, bool]] = [
    ("/detail.html", True),
    ("/detail-blocked.html", True),
    ("/detail-thin.html", False),
    ("/blank.html", False),
]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        html = _PAGES.get(path)
        if html is None:
            self.send_error(404)
            return
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        return


async def _check(page: Any, base: str, path: str, expected: bool, label: str) -> bool:
    await page.goto(f"{base}{path}", wait_until="domcontentloaded")
    arg = list_ready_arg() if label == "列表" else detail_ready_arg()
    js = LIST_READY_JS if label == "列表" else DETAIL_READY_JS
    # 期望命中的用短超时（应立刻返回）；期望不命中的也得给足超时才说明「真的没命中」
    got = await page.wait_for_function(js, arg, timeout_ms=700)
    mark = "OK  " if got is expected else "FAIL"
    print(f"  {mark} {label} {path:22s} 期望={expected!s:5s} 实际={got}")
    return got is expected


async def _main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    port = create_browser("camoufox")
    await port.launch(LaunchOptions(headless=True))
    passed = 0
    total = 0
    try:
        page = await port.open()

        print("列表就绪判据 LIST_READY_JS：")
        for path, expected in _LIST_CASES:
            total += 1
            passed += await _check(page, base, path, expected, "列表")

        print("详情就绪判据 DETAIL_READY_JS：")
        for path, expected in _DETAIL_CASES:
            total += 1
            passed += await _check(page, base, path, expected, "详情")

        await page.close()
    finally:
        await port.close()
        server.shutdown()

    print(f"\n结果：{passed}/{total} 通过")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s: %(message)s")
    asyncio.run(_main())
