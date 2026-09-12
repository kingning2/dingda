"""探测：小红书笔记详情为何 300031 / extract_failed。

职责：
    用账号库 cookie 注入 Camoufox，先搜拿到 note_id + xsec_token，
    再对比「裸开 explore」与「带 xsec_token」两种详情路径，并截获 feed XHR。

设计说明：
    - 独立脚本，不改产品代码；默认有头，方便对照直播画面
    - 不要求账号 connected，只要 auth_valid + cookie

用法：
    cd server
    .venv\\Scripts\\python.exe scripts/probe_xiaohongshu_detail.py
    .venv\\Scripts\\python.exe scripts/probe_xiaohongshu_detail.py --keyword 测试 --headless
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from browser.adapters.camoufox import CamoufoxAdapter  # noqa: E402
from contracts.browser_port import LaunchOptions  # noqa: E402
from channels.cookie_header import parse_cookie_header  # noqa: E402
from channels.xiaohongshu.cookies import to_browser_cookies  # noqa: E402
from infrastructure.db import accounts as account_repo  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("dingda.probe.xhs_detail")

OUT_DIR = _ROOT / "tmp" / "xhs_detail_probe"
NOTE_URL = "https://www.xiaohongshu.com/explore"
SEARCH_URL = "https://www.xiaohongshu.com/search_result"

PAGE_HINT_JS = r"""
() => {
  const text = ((document.body && document.body.innerText) || '').slice(0, 2000);
  const params = new URLSearchParams(location.search || '');
  return {
    url: location.href || '',
    title: document.title || '',
    error_code: params.get('error_code') || '',
    error_msg: params.get('error_msg') || '',
    hasInitialNote: !!(window.__INITIAL_STATE__ && window.__INITIAL_STATE__.note),
    noteMapKeys: window.__INITIAL_STATE__ && window.__INITIAL_STATE__.note
      && window.__INITIAL_STATE__.note.noteDetailMap
      ? Object.keys(window.__INITIAL_STATE__.note.noteDetailMap).slice(0, 5)
      : [],
    login: /登录后|扫码登录|手机号登录|请先登录/.test(text),
    preview: text.replace(/\s+/g, ' ').slice(0, 180),
  };
}
"""


def _pick_cookie() -> tuple[str, str]:
    rows = account_repo.list_accounts(platform="xiaohongshu")
    for row in rows:
        if row.auth_valid and (row.cookie or "").strip():
            return row.account_id, row.cookie.strip()
    for row in rows:
        if (row.cookie or "").strip():
            return row.account_id, row.cookie.strip()
    raise SystemExit("账号库没有小红书 cookie，请先扫码登录")


def _is_feed_url(url: str) -> bool:
    blob = (url or "").lower()
    return "api/sns/web/v1/feed" in blob or "/api/sns/web/v2/feed" in blob


def _is_search_url(url: str) -> bool:
    blob = (url or "").lower()
    return "search/notes" in blob


def _extract_note_from_search(body: dict[str, Any]) -> dict[str, str] | None:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    rows = data.get("items") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        note_id = str(row.get("id") or "")
        card = row.get("note_card") or row.get("noteCard") or {}
        if not isinstance(card, dict):
            card = {}
        if not note_id:
            note_id = str(card.get("note_id") or card.get("id") or "")
        token = str(
            row.get("xsec_token")
            or row.get("xsecToken")
            or card.get("xsec_token")
            or card.get("xsecToken")
            or ""
        )
        title = str(
            card.get("display_title")
            or card.get("displayTitle")
            or card.get("title")
            or row.get("title")
            or ""
        ).strip()
        if len(note_id) >= 16 and title:
            return {"note_id": note_id, "xsec_token": token, "title": title}
    return None


async def _shot(page: Any, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    await page.screenshot(path=path, image_type="jpeg", quality=55)
    return path


async def _goto_and_hint(page: Any, url: str, *, label: str) -> dict[str, Any]:
    logger.info("[%s] goto %s", label, url)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout_ms=35_000)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] goto error: %s", label, exc)
    raw = page.raw
    await raw.wait_for_timeout(2500)
    hint = await raw.evaluate(PAGE_HINT_JS)
    shot = await _shot(page, f"{label}.jpg")
    logger.info("[%s] hint=%s shot=%s", label, json.dumps(hint, ensure_ascii=False), shot.name)
    return hint if isinstance(hint, dict) else {"raw": hint}


async def run_probe(*, keyword: str, headless: bool, keep_open_s: float) -> dict[str, Any]:
    """跑搜索 + 两种详情打开方式，返回摘要。"""
    account_id, cookie = _pick_cookie()
    cookies = to_browser_cookies(parse_cookie_header(cookie))
    logger.info(
        "account=%s cookie_count=%s headless=%s keyword=%s",
        account_id,
        len(cookies or []),
        headless,
        keyword,
    )

    adapter = CamoufoxAdapter()
    await adapter.launch(LaunchOptions(headless=headless))
    page = await adapter.open(cookies=cookies, default_domain=".xiaohongshu.com")
    raw = page.raw

    search_bodies: list[dict[str, Any]] = []
    feed_bodies: list[dict[str, Any]] = []
    pending_search: list[Any] = []
    pending_feed: list[Any] = []

    def _on_response(response: Any) -> None:
        url = str(getattr(response, "url", "") or "")
        method = getattr(getattr(response, "request", None), "method", "")
        if method not in {"GET", "POST"}:
            return
        if _is_search_url(url):
            pending_search.append(response)
            logger.info("命中 search status=%s", getattr(response, "status", "?"))
        elif _is_feed_url(url):
            pending_feed.append(response)
            logger.info("命中 feed status=%s url=%s", getattr(response, "status", "?"), url.split("?", 1)[0])

    raw.on("response", _on_response)

    summary: dict[str, Any] = {
        "account_id": account_id,
        "keyword": keyword,
        "note": None,
        "bare": None,
        "with_token": None,
        "feed_captured": 0,
        "search_captured": 0,
    }

    try:
        search = f"{SEARCH_URL}?{urlencode({'keyword': keyword, 'source': 'web_explore_feed'})}"
        await _goto_and_hint(page, search, label="01_search")
        for _ in range(40):
            while pending_search:
                resp = pending_search.pop(0)
                try:
                    body = await resp.json()
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(body, dict):
                    search_bodies.append(body)
                    summary["search_captured"] = len(search_bodies)
                    note = _extract_note_from_search(body)
                    if note and not summary["note"]:
                        summary["note"] = note
                        logger.info(
                            "选中笔记 id=%s token_len=%s title=%s",
                            note["note_id"],
                            len(note["xsec_token"]),
                            note["title"][:40],
                        )
            if summary["note"]:
                break
            await raw.wait_for_timeout(250)

        note = summary["note"]
        if not note:
            logger.error("搜索未拿到笔记，无法继续详情对比")
            return summary

        note_id = note["note_id"]
        token = note["xsec_token"]

        # A) 裸开（复现现网 product 路径）
        bare_url = f"{NOTE_URL}/{note_id}"
        summary["bare"] = await _goto_and_hint(page, bare_url, label="02_bare")

        # B) 带 xsec_token（pc_search）
        if token:
            qs = urlencode(
                {
                    "xsec_token": token,
                    "xsec_source": "pc_search",
                }
            )
            token_url = f"{NOTE_URL}/{note_id}?{qs}"
            summary["with_token"] = await _goto_and_hint(page, token_url, label="03_with_token")
        else:
            logger.warning("搜索结果没有 xsec_token，跳过带 token 对比")

        # 再等一会儿收 feed
        for _ in range(20):
            while pending_feed:
                resp = pending_feed.pop(0)
                try:
                    body = await resp.json()
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(body, dict):
                    feed_bodies.append(body)
                    summary["feed_captured"] = len(feed_bodies)
                    logger.info(
                        "截获 feed keys=%s code=%s",
                        sorted(body.keys()),
                        body.get("code"),
                    )
            await raw.wait_for_timeout(200)

        if feed_bodies:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / "feed_last.json").write_text(
                json.dumps(feed_bodies[-1], ensure_ascii=False, indent=2)[:80_000],
                encoding="utf-8",
            )

        if keep_open_s > 0 and not headless:
            logger.info("保持窗口 %.0fs 供人工查看…", keep_open_s)
            await raw.wait_for_timeout(int(keep_open_s * 1000))
    finally:
        try:
            raw.remove_listener("response", _on_response)
        except Exception:  # noqa: BLE001
            pass
        await page.close()
        await adapter.close()

    out_path = OUT_DIR / "summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("摘要已写 %s", out_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="探测小红书详情 300031")
    parser.add_argument("--keyword", default="测试")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-open", type=float, default=8.0, help="有头时结束后多留几秒")
    args = parser.parse_args()
    summary = asyncio.run(
        run_probe(
            keyword=args.keyword,
            headless=args.headless,
            keep_open_s=0.0 if args.headless else args.keep_open,
        )
    )
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    bare = summary.get("bare") or {}
    with_token = summary.get("with_token") or {}
    print("\n对比:")
    print(f"  bare error_code={bare.get('error_code')!r} url={bare.get('url', '')[:120]}")
    print(
        f"  token error_code={with_token.get('error_code')!r} "
        f"noteMap={with_token.get('noteMapKeys')} url={str(with_token.get('url', ''))[:120]}"
    )
    print(f"  feed_captured={summary.get('feed_captured')} search_captured={summary.get('search_captured')}")
    print(f"  screenshots -> {OUT_DIR}")


if __name__ == "__main__":
    main()
