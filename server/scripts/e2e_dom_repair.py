"""端到端验证：清空 detail_dom → 走产品 DOM 修复链路 → 与原始抽取结果比对。

职责：
    真机打开详情页，先用【原始】extract.json 抽一遍作真值（baseline）；
    再把 detail_dom 选择器清空（键全保留），逼 AI 从零重定位；
    用产品同一套 repair_detail_dom 修复并写回，最后跟 baseline 逐字段比对。

用法：
    cd server
    .venv\\Scripts\\python.exe scripts/e2e_dom_repair.py --platform xianyu --item-id 1027680267393
    .venv\\Scripts\\python.exe scripts/e2e_dom_repair.py --platform xiaohongshu --keyword 咖啡 --headed
    .venv\\Scripts\\python.exe scripts/e2e_dom_repair.py --platform xianyu --item-id 1 --runtime claude --keep

设计说明：
    - 不改产品代码：只做「清空配置 → 跑产品修复 → 比对」的外壳
    - 真机 + 真 AI：会启 Camoufox 并调外部 CLI（默认 codex）
    - 默认用临时空白指纹库，确保走 AI 而非指纹短路径（--use-real-fingerprints 复用真库）
    - 结束后还原 extract.json（--keep 保留 AI 写回的现场）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.browser.adapters.camoufox import CamoufoxAdapter  # noqa: E402
from src.browser.port import LaunchOptions, Page  # noqa: E402
from src.channels.cookie_header import parse_cookie_header  # noqa: E402
from src.crawler.core.base import BrowserSessionOptions  # noqa: E402
from src.crawler.core.types import CrawlContext  # noqa: E402
from src.crawler.extraction import fingerprint as fp  # noqa: E402
from src.crawler.extraction.config import reload_extract_json  # noqa: E402
from src.crawler.extraction.repair.orchestrator import repair_detail_dom  # noqa: E402
from src.crawler.extraction.repair.types import RepairResult  # noqa: E402
from src.crawler.registry import cookies_for, create_crawler  # noqa: E402
from src.infrastructure.db import accounts as account_repo  # noqa: E402
from src.shared.errors import AppError  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("dingda.e2e.dom_repair")


def _force_utf8_console() -> None:
    """Windows 控制台默认 GBK，打不出 ``¥`` 等字符会崩，这里强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_force_utf8_console()

OUT_DIR = _ROOT / "tmp" / "e2e_dom_repair"

# 每平台：要清空的选择器键、要比对的字段、详情页 URL 参数。
_SOURCES: dict[str, dict[str, Any]] = {
    "xianyu": {
        "extract": _ROOT / "src" / "crawler" / "sources" / "xianyu" / "extract.json",
        "blank": [
            "root",
            "info",
            "price",
            "want",
            "desc",
            "labels",
            "seller_nick",
            "seller_intro",
            "img",
        ],
        "compare": ["title", "description", "price", "want_count", "seller_name"],
        "url": "https://www.goofish.com/item",
        "id_param": "id",
    },
    "xiaohongshu": {
        "extract": (
            _ROOT / "src" / "crawler" / "sources" / "xiaohongshu" / "extract.json"
        ),
        "blank": ["author", "title", "card"],
        "compare": ["title", "author"],
        "url": "https://www.xiaohongshu.com/explore",
        "id_param": "xsec_token",
    },
}


def _cookie_for(platform: str) -> str:
    """取账号库里第一个可用 cookie。"""
    rows = account_repo.list_accounts(platform=platform)
    for row in rows:
        if row.auth_valid and (row.cookie or "").strip():
            return row.cookie.strip()
    for row in rows:
        if (row.cookie or "").strip():
            return row.cookie.strip()
    raise SystemExit(f"账号库没有 {platform} 的 cookie，先在应用里登录")


def _extract_cfg(platform: str) -> dict[str, Any]:
    return json.loads(_SOURCES[platform]["extract"].read_text(encoding="utf-8"))


def _cookie_domain(platform: str) -> str:
    urls = _extract_cfg(platform).get("urls")
    if isinstance(urls, dict) and urls.get("cookie_domain"):
        return str(urls["cookie_domain"])
    return ".goofish.com" if platform == "xianyu" else ".xiaohongshu.com"


def _flatten(platform: str, payload: dict[str, Any] | None) -> dict[str, str]:
    """把平台 payload 收成可比的扁平字段表。"""
    payload = payload or {}
    if platform == "xianyu":
        out = {
            key: str(payload.get(key) or "").strip()
            for key in _SOURCES["xianyu"]["compare"]
        }
        images = payload.get("image_urls")
        out["images"] = str(len(images)) if isinstance(images, list) else "0"
        return out
    note = payload.get("note") if isinstance(payload.get("note"), dict) else {}
    user = note.get("user") if isinstance(note.get("user"), dict) else {}
    return {
        "title": str(note.get("title") or "").strip(),
        "author": str(user.get("nickname") or "").strip(),
    }


_PAGE_STATE_JS = r"""
() => ({
  url: location.href,
  title: document.title,
  head: String((document.body && document.body.innerText) || '')
    .replace(/\s+/g, ' ').trim().slice(0, 160),
  itemInfo: !!document.querySelector('[class*="item-main-info"]'),
})
"""


async def _page_state(view: Page) -> dict[str, Any]:
    """页面到底渲染出了什么 —— 给「baseline 全空」做诊断。"""
    try:
        raw = await view.evaluate(_PAGE_STATE_JS)
    except Exception:  # noqa: BLE001
        logger.debug("page state probe failed", exc_info=True)
        return {}
    return raw if isinstance(raw, dict) else {}


def _blank_selectors(section: dict[str, Any], keys: list[str], mode: str) -> dict[str, Any]:
    """按 mode 清空指定键：empty → 空串；stale → 过期选择器。"""
    out = dict(section)
    for key in keys:
        out[key] = "" if mode == "empty" else f"#stale-{key}"
    return out


def _write_extract(platform: str, mutate: Any) -> None:
    """读原配置 → mutate → 原子写回 → 刷新进程内缓存。"""
    path = _SOURCES[platform]["extract"]
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg = mutate(cfg)
    path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    reload_extract_json(path)


def _raw_view(platform: str, raw: Any, page: Page | None = None) -> Page:
    """复用产品里的 _RawPageView，把底层 Playwright page 接进修复编排。"""
    if platform == "xianyu":
        from src.crawler.sources.xianyu.crawler import _RawPageView

        return _RawPageView(raw)
    from src.crawler.sources.xiaohongshu.crawler import _RawPageView as XhsView

    return XhsView(raw, page)


def _adapter(platform: str) -> Any:
    if platform == "xianyu":
        from src.crawler.sources.xianyu.crawler import _XIANYU_ADAPTER

        return _XIANYU_ADAPTER
    from src.crawler.sources.xiaohongshu.crawler import _XHS_ADAPTER

    return _XHS_ADAPTER


async def _pass_platform_risk(platform: str, page: Page) -> None:
    """补跑一遍平台的风控恢复。

    ``repair`` 模式绕开了 crawler（直接调 evaluate_extract），也就绕开了
    ``_pass_risk_or_raise`` —— 于是风控页上 baseline 会全空，看着像「商品没了」。
    这里把产品那条恢复链路补上：自动滑块 → （有头时）人工窗。
    """
    if platform == "xianyu":
        from src.crawler.sources.xianyu.crawler import _pass_risk_or_raise

        await _pass_risk_or_raise(page, where="e2e")
        return
    from src.crawler.sources.xiaohongshu.crawler import _XHS_RISK

    await _XHS_RISK.recover_risk(page, where="e2e", url=page.url)


async def _resolve_xianyu_target(
    port: CamoufoxAdapter,
    cookie: str,
    keyword: str,
) -> str:
    """没给 item-id 就现搜一个 —— 固定的 id 会下架，搜出来的才是活的。"""
    crawler = create_crawler(
        "xianyu",
        port,
        BrowserSessionOptions(
            cookies=cookies_for("xianyu", cookie),
            cookie_domain=".goofish.com",
        ),
    )
    result = await crawler.search(
        CrawlContext(task_id="e2e-dom-repair", meta={"limit": 5}),
        keyword,
    )
    for item in result.items:
        if item.item_id:
            logger.info("用搜索结果 target item_id=%s", item.item_id)
            return item.item_id
    raise SystemExit(f"关键词 {keyword!r} 搜不到商品")


async def _resolve_xhs_target(
    port: CamoufoxAdapter,
    cookie: str,
    keyword: str,
) -> tuple[str, str]:
    """搜一条笔记，拿到 (note_id, xsec_token)——详情必须带 token 才能开。"""
    crawler = create_crawler(
        "xiaohongshu",
        port,
        BrowserSessionOptions(
            cookies=cookies_for("xiaohongshu", cookie),
            cookie_domain=".xiaohongshu.com",
        ),
    )
    result = await crawler.search(
        CrawlContext(task_id="e2e-dom-repair", meta={"limit": 5}),
        keyword,
    )
    for item in result.items:
        token = str((item.raw or {}).get("xsec_token") or "").strip()
        if item.item_id and token:
            logger.info("用搜索结果 target note_id=%s", item.item_id)
            return item.item_id, token
    raise SystemExit(f"关键词 {keyword!r} 搜不到带 xsec_token 的笔记")


async def _open_detail(
    port: CamoufoxAdapter,
    platform: str,
    item_id: str,
    xsec_token: str,
) -> Page:
    spec = _SOURCES[platform]
    page = await port.open(
        cookies=cookies_for(platform, _cookie_for(platform)),
        default_domain=_cookie_domain(platform),
    )
    params = {"id": item_id} if platform == "xianyu" else {
        "xsec_token": xsec_token,
        "xsec_source": "pc_search",
    }
    url = f"{spec['url']}?{_qs(params)}"
    logger.info("goto %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout_ms=45_000)
    await getattr(page, "raw", page).wait_for_timeout(6000)
    return page


def _qs(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return urlencode(params)


async def _run(args: argparse.Namespace) -> int:
    platform = args.platform
    spec = _SOURCES[platform]
    extract_path = spec["extract"]
    # 备份必须放到仓库外。修复子 agent 的 cwd 就是仓库，且本机 codex 走
    # --sandbox danger-full-access；把原始配置留在 extract.json 旁边 = 直接把答案递给它。
    scratch = Path(tempfile.mkdtemp(prefix="e2e-dom-repair-"))
    backup = scratch / f"{platform}-extract.json"
    shutil.copy2(extract_path, backup)

    fingerprint_backup: Path | None = None
    if args.use_real_fingerprints:
        fingerprint_backup = fp._store_path()
    else:
        tmp_store = Path(tempfile.mkdtemp(prefix="e2e-fp-")) / "dom_fingerprints.json"
        fp._STORE = tmp_store
        logger.info("用临时空白指纹库 %s", tmp_store)

    port = CamoufoxAdapter()
    artifact: dict[str, Any] = {
        "platform": platform,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "blank_mode": args.blank,
    }
    verdict = 1
    try:
        await port.launch(LaunchOptions(headless=not args.headed))

        item_id = str(args.item_id or "").strip()
        xsec_token = ""
        if platform == "xiaohongshu":
            item_id, xsec_token = await _resolve_xhs_target(
                port, _cookie_for(platform), args.keyword
            )
        elif not item_id:
            # 没给 id 就现搜一个：固定的 id 会下架，页面变成「为你推荐」兜底页
            item_id = await _resolve_xianyu_target(
                port, _cookie_for(platform), args.keyword
            )
        if not item_id:
            raise SystemExit("--item-id 必填（不给则用 --keyword 现搜一个）")
        artifact["item_id"] = item_id

        adapter = _adapter(platform)

        # 1) 真值：原始配置抽一遍（crawler 模式走产品 detail()，弹层才真渲染）
        if args.mode == "repair":
            page = await _open_detail(port, platform, item_id, xsec_token)
            view = _raw_view(platform, getattr(page, "raw", page), page)
            # 风控页上详情区不渲染 → baseline 全空。先照产品那样过一遍风控再抽。
            if platform == "xianyu" and not (await _page_state(view)).get("itemInfo"):
                logger.warning("页面暂无商品信息，先走平台风控恢复（同产品链路）…")
                await _pass_platform_risk(platform, page)
                await getattr(page, "raw", page).wait_for_timeout(2500)
            base_payload = await adapter.evaluate_extract(
                view, adapter.current_selectors(), item_id=item_id
            )
        else:
            base_payload = await _crawler_detail(port, platform, item_id, xsec_token)
        flat_base = _flatten(platform, base_payload)
        artifact["baseline"] = flat_base
        logger.info("baseline=%s", json.dumps(flat_base, ensure_ascii=False))
        if not any(flat_base.get(key) for key in spec["compare"]):
            state = await _page_state(view) if args.mode == "repair" else {}
            artifact["page_state"] = state
            logger.error(
                "baseline 全空：页面上没有可抽的内容 —— 本次比对无意义。url=%s title=%s",
                state.get("url", "?"),
                state.get("title", "?"),
            )
            if state and not state.get("itemInfo"):
                logger.error(
                    "%s 的商品信息区（item-main-info）不存在，页面是「为你推荐」兜底 → "
                    "该 item 大概已下架/卖出/被删。换一个 --item-id 再跑。",
                    item_id,
                )
            logger.error("页面开头：%s", str(state.get("head") or "")[:120])
            print("\n跳过：页面无内容（item 可能已失效），换 --item-id 再试")
            return 2

        # 2) 清空 detail_dom（键保留），刷缓存
        _write_extract(
            platform,
            lambda cfg: {
                **cfg,
                "detail_dom": _blank_selectors(
                    cfg.get("detail_dom") or {}, spec["blank"], args.blank
                ),
            },
        )
        logger.info("已清空 %s 的 detail_dom（mode=%s）", platform, args.blank)
        selectors_before = adapter.current_selectors()

        # 3) 走产品修复链路
        if args.mode == "repair":
            result = await repair_detail_dom(view, adapter, item_id=item_id)
            flat_after = _flatten(platform, result.payload)
        else:
            after_payload = await _crawler_detail(port, platform, item_id, xsec_token)
            flat_after = _flatten(platform, after_payload)
            result = RepairResult(
                ok=bool(any(flat_after.get(key) for key in spec["compare"])),
                payload=after_payload,
            )
            artifact["config_changed"] = adapter.current_selectors() != selectors_before

        artifact["repair_ok"] = result.ok
        artifact["repair_error"] = result.error
        artifact["patch_source"] = result.patch.source if result.patch else None
        if result.patch is not None:
            artifact["patch"] = {
                k: v for k, v in result.patch.selectors.items() if isinstance(v, str)
            }
        elif artifact.get("config_changed"):
            # crawler 模式的补丁写在编排内部，取落盘后的现场
            artifact["patch"] = adapter.current_selectors()
        artifact["after"] = flat_after
        logger.info(
            "repair ok=%s error=%s source=%s",
            result.ok,
            result.error,
            artifact["patch_source"],
        )

        diffs = _diff(flat_base, flat_after, spec["compare"])
        artifact["diffs"] = diffs
        _print_report(flat_base, flat_after, spec["compare"], diffs, result)
        verdict = 0 if result.ok and not diffs else 1
    finally:
        try:
            await port.close()
        except Exception:  # noqa: BLE001
            logger.debug("port close failed", exc_info=True)
        if not args.keep:
            shutil.copy2(backup, extract_path)
            reload_extract_json(extract_path)
            backup.unlink(missing_ok=True)
            logger.info("已还原 extract.json")
        else:
            backup.unlink(missing_ok=True)
            logger.info("--keep：保留 AI 写回的 extract.json")
        if fingerprint_backup is not None:
            fp._STORE = fingerprint_backup

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"{platform}_{artifact.get('item_id', 'x')}_{stamp}.json"
    out_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n产物：{out_path}")
    print(f"结论：{'PASS ✅' if verdict == 0 else 'FAIL ❌'}")
    return verdict


async def _crawler_detail(
    port: CamoufoxAdapter,
    platform: str,
    item_id: str,
    xsec_token: str,
) -> dict[str, Any]:
    """顶层链路：调平台 crawler.detail()，返回与修复编排同口径的 payload。"""
    cookie = _cookie_for(platform)
    crawler = create_crawler(
        platform,
        port,
        BrowserSessionOptions(
            cookies=cookies_for(platform, cookie),
            cookie_domain=_cookie_domain(platform),
        ),
    )
    ctx = CrawlContext(
        task_id="e2e-dom-repair",
        meta={"cookie": cookie, "xsec_token": xsec_token},
    )
    if platform == "xianyu":
        # 闲鱼 detail 优先 mtop，页内 lib.mtop 也常直接成功 → 都堵掉才落到 DOM 兜底
        from unittest.mock import patch

        _write_extract(
            "xianyu",
            lambda cfg: {**cfg, "view": {**(cfg.get("view") or {}), "api": ""}},
        )
        with patch(
            "src.crawler.sources.xianyu.crawler.mtop_call",
            side_effect=AppError(
                "channel.mtop_failed", "e2e 强制走 DOM 兜底", status_code=502
            ),
        ):
            crawl = await crawler.detail(ctx, item_id)
    else:
        crawl = await crawler.detail(ctx, item_id)

    item = crawl.items[0] if crawl.items else None
    if item is None:
        return {}
    if platform == "xianyu":
        # item_from_view 把 DETAIL_DOM_JS 的 payload 放在 raw["view"]
        view = (item.raw or {}).get("view")
        return view if isinstance(view, dict) else {}
    # item_from_detail 把笔记 dict 放在 raw["note"]
    return {"note": (item.raw or {}).get("note") or {}}


def _diff(base: dict[str, str], after: dict[str, str], fields: list[str]) -> list[str]:
    """比对核心字段：任一侧为空或两侧不等都算差异。"""
    diffs: list[str] = []
    for key in fields:
        b = (base.get(key) or "").strip()
        a = (after.get(key) or "").strip()
        if not a or a != b:
            diffs.append(key)
    return diffs


def _print_report(
    base: dict[str, str],
    after: dict[str, str],
    fields: list[str],
    diffs: list[str],
    result: RepairResult,
) -> None:
    print("\n" + "=" * 72)
    print(f"{'字段':<16}{'原始(baseline)':<26}{'AI 修复后':<26}{'一致'}")
    print("-" * 72)
    for key in fields:
        b = base.get(key, "")
        a = after.get(key, "")
        mark = "✓" if key not in diffs else "✗"
        print(f"{key:<16}{_clip(b):<26}{_clip(a):<26}{mark}")
    print("-" * 72)
    print(f"修复成功：{result.ok}   补丁来源：{result.patch.source if result.patch else '-'}")
    if result.error:
        print(f"错误码：{result.error}")
    if diffs:
        print(f"不一致字段：{', '.join(diffs)}")
    print("=" * 72)


def _clip(text: str, width: int = 24) -> str:
    text = str(text or "").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="清空 detail_dom → AI 自动修复 → 与原始抽取比对",
    )
    parser.add_argument("--platform", choices=sorted(_SOURCES), required=True)
    parser.add_argument("--item-id", default="", help="闲鱼商品 id；小红书可省略")
    parser.add_argument("--keyword", default="测试", help="小红书搜词（取 note_id + token）")
    parser.add_argument(
        "--mode",
        choices=["repair", "crawler"],
        default="repair",
        help="repair=直接跑修复编排（确定）；crawler=跑平台 detail() 顶层链路",
    )
    parser.add_argument(
        "--blank",
        choices=["empty", "stale"],
        default="empty",
        help="empty=选择器清空；stale=塞过期选择器",
    )
    parser.add_argument(
        "--runtime",
        default="",
        help="外部 CLI：codex / claude / opencode；不给则跟随应用里用户选的 agent",
    )
    parser.add_argument("--rounds", type=int, default=3, help="AI 修复轮数上限")
    parser.add_argument("--headed", action="store_true", help="有头（可看直播画面）")
    parser.add_argument("--keep", action="store_true", help="保留 AI 写回的 extract.json")
    parser.add_argument(
        "--use-real-fingerprints",
        action="store_true",
        help="复用真实指纹库（默认为空库，强制走 AI）",
    )
    args = parser.parse_args()

    if args.runtime.strip():
        os.environ["DINGDA_DOM_REPAIR_RUNTIME"] = args.runtime.strip()
    else:
        # 不指定就清掉，让子 agent 跟随用户在选择里配的 agent
        os.environ.pop("DINGDA_DOM_REPAIR_RUNTIME", None)
    os.environ["DINGDA_DOM_REPAIR_ROUNDS"] = str(args.rounds)
    os.environ.setdefault("DINGDA_DOM_REPAIR", "1")

    code = asyncio.run(_run(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
