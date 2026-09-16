"""探针：在真实 Camoufox 上验证 BrowserPort 的等待原语与事件层。

职责：
    排障 / 回归用。用本地 HTTP 页（不碰任何平台，不触发风控）验证：
    ① ``wait_for_function`` 传 ``(arg) => …`` 时是否**真的在等**——若被引擎当成
       普通表达式求值，会拿到 truthy 的函数对象而立即返回，等于没等待；
    ② 各等待原语超时是否返回 False/None 而不抛；
    ③ ``on`` / ``wait_for_event`` 能否捕获响应、页面异常，以及日志是否照常打出。

使用示例：
    python -m api.scripts.probe_page_waits
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from browser.registry import create_browser
from contracts.browser_port import LaunchOptions, PageEvent, PageEventInfo

# 页面里延迟 1.2s 才插入 #late，用来区分「真在等」与「立即返回」
_INDEX = """<!doctype html><html><body>
<div id="early">early</div>
<script>
  setTimeout(function () {
    var d = document.createElement('div');
    d.id = 'late';
    d.textContent = 'late';
    document.body.appendChild(d);
  }, 1200);
  fetch('/probe').catch(function () {});
  fetch('/missing').catch(function () {});
  setTimeout(function () { throw new Error('boom-from-page'); }, 300);
</script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/index.html"):
            self._send(200, "text/html; charset=utf-8", _INDEX.encode())
        elif self.path.startswith("/probe"):
            self._send(200, "application/json", json.dumps({"ok": True}).encode())
        else:
            self._send(404, "text/plain", b"nope")

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        return


async def _main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"本地服务 {base}")

    port = create_browser("camoufox")
    await port.launch(LaunchOptions(headless=True))
    try:
        page = await port.open()

        responses: list[PageEventInfo] = []
        failed: list[PageEventInfo] = []
        page_errors: list[PageEventInfo] = []
        page.on(PageEvent.RESPONSE, responses.append)
        page.on(PageEvent.REQUEST_FAILED, failed.append)
        page.on(PageEvent.PAGE_ERROR, page_errors.append)

        # 导航类事件必须在 goto 之前挂，否则会错过
        waiter = asyncio.create_task(
            page.wait_for_event(PageEvent.RESPONSE, url_contains="/probe", timeout_ms=8_000)
        )

        started = time.perf_counter()
        await page.goto(f"{base}/index.html", wait_until="domcontentloaded")
        print(f"[0] goto 耗时 {time.perf_counter() - started:.2f}s")

        started = time.perf_counter()
        ok = await page.wait_for_function(
            "(sel) => !!document.querySelector(sel)",
            "#late",
            timeout_ms=8_000,
        )
        waited = time.perf_counter() - started
        print(f"[1] wait_for_function 等 #late: ok={ok} 实等={waited:.2f}s（应≈1.2s，不是 0）")

        started = time.perf_counter()
        ok = await page.wait_for_function(
            "(sel) => !!document.querySelector(sel)",
            "#early",
            timeout_ms=8_000,
        )
        print(f"[2] 条件已成立: ok={ok} 实等={time.perf_counter() - started:.2f}s（应≈0）")

        started = time.perf_counter()
        ok = await page.wait_for_function(
            "(sel) => !!document.querySelector(sel)",
            "#nope",
            timeout_ms=700,
        )
        print(f"[3] 超时: ok={ok} 实等={time.perf_counter() - started:.2f}s（应 False，不抛）")

        print(f"[4] wait_for_selector 超时: {await page.wait_for_selector('#nope', timeout_ms=700)}（应 False）")
        print(f"[5] wait_for_selector 命中: {await page.wait_for_selector('#early', timeout_ms=2_000)}（应 True）")
        print(f"[6] wait_for_load_state: {await page.wait_for_load_state(timeout_ms=3_000)}（应 True）")

        info = await waiter
        print(
            "[7] wait_for_event(/probe) 导航前挂起: "
            f"url={info.url if info else None} status={info.status if info else None}"
        )

        await asyncio.sleep(1.2)
        marks = [f"{r.status} {r.url.split('?')[0].rsplit('/', 1)[-1]}" for r in responses]
        print(f"[8] on(RESPONSE) 收到 {len(responses)} 条: {marks}")
        print(f"[9] on(REQUEST_FAILED) 收到 {len(failed)} 条（404 属有响应，不该进这里）")
        print(f"[10] on(PAGE_ERROR) 收到 {len(page_errors)} 条: "
              f"{[e.message[:40] for e in page_errors]}")

        page.on(PageEvent.RESPONSE, lambda _i: None)()
        print("[11] 订阅后立即取消：未报错")

        await page.close()
    finally:
        await port.close()
        server.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    asyncio.run(_main())
