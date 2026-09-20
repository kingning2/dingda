"""修复 Agent 真实浏览器 E2E。

职责：
    用 Camoufox 打开本地新版详情页，验证修复子 agent 能看到最新 DOM；
    验证子 agent 用现有平台抽取代码试跑候选并热更新。

设计说明：
    - 页面在本地启动，避免访问闲鱼/小红书或依赖外部网站
    - 只替换抽取配置落点，浏览器与修复/验证工具全部走真实链路
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from langchain_core.messages import AIMessage

import agent.session as agent_session
from agent.subagents.repair import run_repair
from agent.subagents.validator import run_validate
from browser.manager import BrowserManager
from crawler.sources.xianyu.repair_adapter import XianyuDetailRepairAdapter
from tests.integration._support import FakeLlm, ScriptedChat, make_ctx


_LATEST_HTML = """<!doctype html>
<html>
  <head><title>手工露营折叠桌_闲鱼</title></head>
  <body>
    <div class="stale-info">
      <span class="stale-title"></span>
      <span class="stale-price"></span>
    </div>
    <div class="repaired-info">
      <span class="repaired-title">手工露营折叠桌</span>
      <span class="repaired-price">188</span>
      <span class="repaired-want">12人想要 99浏览</span>
      <span class="repaired-desc">这是本地新版页面里的最新描述</span>
      <span class="repaired-seller">叮答测试卖家</span>
    </div>
  </body>
</html>
"""


class _LatestPageHandler(BaseHTTPRequestHandler):
    """返回新版商品详情页的本地 HTTP 处理器。"""

    def do_GET(self) -> None:
        """只响应 /item；查询参数仅用于确认真实导航发生。"""
        parsed = urlparse(self.path)
        if parsed.path != "/item" or parse_qs(parsed.query).get("id") != ["7"]:
            self.send_error(404)
            return
        body = _LATEST_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """静默本地服务日志。"""
        return


@pytest.mark.integration
def test_repair_agent_reads_latest_dom_and_validates_with_real_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """失效选择器抽不到新页面，修复后现有抽取代码能拿到最新价格。"""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LatestPageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    beside = tmp_path / "extract.json"
    beside.write_text(
        json.dumps(
            {
                "detail_dom": {
                    "info": ".stale-info",
                    "price": ".stale-price",
                    "want": ".stale-want",
                    "desc": ".stale-desc",
                    "seller_nick": ".stale-seller",
                    "ready_timeout_ms": 100,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(XianyuDetailRepairAdapter, "extract_beside", beside)
    monkeypatch.setattr("crawler.sources.xianyu.extractor.ITEM_URL", f"{base_url}/item")

    manager = BrowserManager(max_browsers=1, max_contexts_per_browser=1)
    monkeypatch.setattr(agent_session, "get_browser_manager", lambda: manager)
    old_selectors = {
        "title": ".stale-title",
        "price": ".stale-price",
    }
    new_selectors = {
        "title": ".repaired-title",
        "price": ".repaired-price",
        "want": ".repaired-want",
        "desc": ".repaired-desc",
        "seller_nick": ".repaired-seller",
    }
    repair_llm = FakeLlm(
        ScriptedChat(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "inspect_dom",
                            "args": {"platform": "xianyu", "item_id": "7"},
                            "id": "inspect-1",
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "submit_patch",
                            "args": {"platform": "xianyu", "item_id": "7", "selectors": new_selectors},
                            "id": "submit-1",
                        }
                    ],
                ),
            ]
        )
    )
    validate_llm = FakeLlm(
        ScriptedChat(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "try_selectors",
                            "args": {"platform": "xianyu", "item_id": "7", "selectors": new_selectors},
                            "id": "try-1",
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "commit_selectors",
                            "args": {"platform": "xianyu", "selectors": new_selectors},
                            "id": "commit-1",
                        }
                    ],
                ),
                AIMessage(content="候选选择器已通过并热更新"),
            ]
        )
    )

    try:
        loop = asyncio.new_event_loop()
        try:
            old_result = loop.run_until_complete(
                _validate_payload(base_url, old_selectors, manager)
            )
            assert old_result.get("valid") is False
            assert old_result.get("payload", {}).get("price") == ""

            repaired = loop.run_until_complete(
                run_repair(
                    make_ctx(llm=repair_llm),
                    platform="xianyu",
                    item_id="7",
                )
            )
            assert repaired["ok"] is True
            assert repaired["selectors"] == new_selectors
            assert ".repaired-price" in json.dumps(repaired)

            validated = loop.run_until_complete(
                run_validate(
                    make_ctx(llm=validate_llm),
                    platform="xianyu",
                    item_id="7",
                    selectors=new_selectors,
                )
            )
            assert validated["ok"] is True
            assert validated["valid"] is True
            assert validated["hot_reloaded"] is True

            latest_result = loop.run_until_complete(
                _validate_payload(base_url, new_selectors, manager)
            )
            assert latest_result.get("valid") is True
            assert latest_result.get("payload", {}).get("price") == "¥188"
        finally:
            loop.run_until_complete(manager.stop())
            loop.close()

        written = json.loads(beside.read_text(encoding="utf-8"))
        assert written["detail_dom"]["price"] == ".repaired-price"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


async def _validate_payload(base_url: str, selectors: dict[str, Any], manager: BrowserManager) -> dict[str, Any]:
    """直接执行现有平台抽取代码，确认选择器在真实页面上是否有效。"""
    adapter = XianyuDetailRepairAdapter()
    async with agent_session.crawl_session(
        "xianyu",
        ctx=make_ctx(),
        headless=True,
    ) as session:
        page = await session.crawler.open_page(session.ctx())
        try:
            await page.goto(f"{base_url}/item?id=7")
            payload = await adapter.evaluate_extract(page, selectors, item_id="7")
        finally:
            await session.crawler.close_page(page)
    valid = adapter.payload_ok(payload)
    return {"valid": valid, "payload": payload}
