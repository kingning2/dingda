"""1688 clawhub 扫码取 AK 页面原语。

职责：
    打开 clawhub、点登录、截二维码、等待登录成功、点钥匙抽 AK。
    经 browser.sync 的 Playwright 页操作，不含扫码状态机。

设计说明：
    - 登录框右侧二维码在淘宝 passport iframe（#alibaba-login-box）内
    - 主文档几乎没有可用二维码 img，必须进 frame 截取
"""

from __future__ import annotations

import base64
import logging
import re
import time
from typing import Any

from src.channels.ali1688.ak import extract_ak_keys

logger = logging.getLogger("dingda.channel.ali1688.login")

CLAWHUB_URL = "https://clawhub.1688.com/"
_LOGIN_IFRAME_ID = "alibaba-login-box"
_AK_PATTERN = re.compile(r"[A-Za-z0-9_\-=]{40,}")


def open_login_modal(page: Any, *, timeout_ms: int = 25_000) -> None:
    """打开 clawhub 并弹出登录框，等到淘宝登录 iframe 可见。"""
    page.goto(CLAWHUB_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(1000)
    _click_login(page)
    _wait_login_iframe(page, timeout_ms=timeout_ms)
    logger.info("clawhub 登录弹窗已打开")


def _click_login(page: Any) -> None:
    """点击顶栏「登录」。"""
    clicked = page.evaluate(
        """() => {
          const nodes = [...document.querySelectorAll('a,button,div,span')];
          const login = nodes.find(e => (e.textContent || '').trim() === '登录');
          if (!login) return false;
          login.click();
          return true;
        }"""
    )
    if not clicked:
        raise RuntimeError("未找到「登录」入口")


def _wait_login_iframe(page: Any, *, timeout_ms: int) -> None:
    """等到 #alibaba-login-box 出现且有尺寸（弹窗真正展开）。"""
    deadline = time.monotonic() + timeout_ms / 1000
    last = ""
    while time.monotonic() < deadline:
        info = page.evaluate(
            """() => {
              const f = document.querySelector('#alibaba-login-box');
              if (!f) return {ok:false, reason:'no-iframe'};
              const r = f.getBoundingClientRect();
              if (r.width < 80 || r.height < 80) {
                return {ok:false, reason:'iframe-too-small', w:r.width, h:r.height};
              }
              return {ok:true, w:r.width, h:r.height};
            }"""
        )
        if isinstance(info, dict) and info.get("ok"):
            logger.info(
                "登录 iframe 已可见 size=%sx%s",
                info.get("w"),
                info.get("h"),
            )
            page.wait_for_timeout(1500)
            return
        last = str(info)
        # 偶发点登录未展开：再点一次
        if "no-iframe" in last or "too-small" in last:
            try:
                _click_login(page)
            except Exception:
                pass
        page.wait_for_timeout(400)
    raise RuntimeError(f"登录弹窗未展开（淘宝登录 iframe 不可见）: {last}")


def find_login_frame(page: Any) -> Any | None:
    """找到淘宝/1688 登录 iframe 对应的 Frame。"""
    for frame in page.frames:
        url = (frame.url or "").lower()
        name = (getattr(frame, "name", None) or "").lower()
        if "login.taobao.com" in url or "login.1688.com" in url or "passport" in url:
            return frame
        if name == _LOGIN_IFRAME_ID:
            return frame
    # 按 element 挂 frame
    try:
        handle = page.query_selector(f"#{_LOGIN_IFRAME_ID}")
        if handle is not None:
            content = handle.content_frame()
            if content is not None:
                return content
    except Exception:
        pass
    return None


def capture_qr_base64(page: Any, *, timeout_ms: int = 25_000) -> str:
    """从登录 iframe 内取得可用二维码 PNG base64（无 data: 前缀）。

    只收「像二维码」的近似正方形图；拒绝空白 canvas / 带 logo 的整块右侧面板。
    """
    deadline = time.monotonic() + timeout_ms / 1000
    last_err: Exception | None = None
    panel_after = time.monotonic() + 8.0

    while time.monotonic() < deadline:
        try:
            frame = find_login_frame(page)
            if frame is None:
                page.wait_for_timeout(400)
                continue

            # 1) canvas.toDataURL / 已加载 img
            encoded = _qr_from_frame_dom(frame)
            if encoded and _b64_looks_like_qr(encoded):
                logger.info("二维码截取 via=frame-dom b64_len=%s", len(encoded))
                return encoded

            # 2) 直接截 canvas 元素（比整块面板干净）
            png = _screenshot_canvas(frame)
            if png and _png_looks_like_qr(png):
                logger.info("二维码截取 via=canvas-screenshot bytes=%s", len(png))
                return base64.b64encode(png).decode("ascii")

            # 3) 其它已加载二维码节点
            png = _screenshot_loaded_qr(frame)
            if png and _png_looks_like_qr(png):
                logger.info("二维码截取 via=element-screenshot bytes=%s", len(png))
                return base64.b64encode(png).decode("ascii")

            # 4) 最后才截右侧面板，且要过像素校验（通常含 logo 会被拒）
            if time.monotonic() >= panel_after:
                png = _screenshot_iframe_qr_panel(page)
                if png and _png_looks_like_qr(png):
                    logger.info("二维码截取 via=iframe-qr-panel bytes=%s", len(png))
                    return base64.b64encode(png).decode("ascii")
        except Exception as exc:
            last_err = exc
            logger.debug("二维码截取重试: %s", exc)
        page.wait_for_timeout(400)

    raise RuntimeError(f"未能截取扫码二维码: {last_err}")


def _qr_from_frame_dom(frame: Any) -> str | None:
    """从 iframe DOM 直接拿 dataURL 或可下载的 img.src。"""
    info = frame.evaluate(
        """() => {
          const canvases = [...document.querySelectorAll('canvas')];
          for (const c of canvases) {
            const w = c.width || c.offsetWidth;
            const h = c.height || c.offsetHeight;
            if (w >= 100 && h >= 100) {
              try {
                return { kind: 'data', data: c.toDataURL('image/png') };
              } catch (e) {}
            }
          }
          const imgs = [...document.querySelectorAll('img')];
          let best = null;
          for (const img of imgs) {
            if (!img.complete || img.naturalWidth < 80 || img.naturalHeight < 80) continue;
            const r = img.getBoundingClientRect();
            if (r.width < 80 || r.height < 80) continue;
            const ratio = r.width / r.height;
            if (ratio < 0.7 || ratio > 1.4) continue;
            const area = r.width * r.height;
            if (!best || area > best.area) {
              best = { kind: 'src', src: img.currentSrc || img.src || '', area };
            }
          }
          return best;
        }"""
    )
    if not isinstance(info, dict):
        return None

    if info.get("kind") == "data":
        data = str(info.get("data") or "")
        if data.startswith("data:image"):
            _, _, payload = data.partition(",")
            payload = payload.strip()
            if payload and len(payload) > 100:
                return payload
        return None

    if info.get("kind") == "src":
        src = str(info.get("src") or "").strip()
        if src.startswith("data:image"):
            _, _, payload = src.partition(",")
            payload = payload.strip()
            return payload or None
        if src.startswith("http://") or src.startswith("https://"):
            try:
                from urllib.request import urlopen

                with urlopen(src, timeout=10) as resp:
                    raw = resp.read()
                if raw[:3] == b"\xff\xd8\xff":
                    raw = _jpeg_to_png(raw)
                if _is_valid_png(raw):
                    return base64.b64encode(raw).decode("ascii")
            except Exception as exc:
                logger.debug("下载二维码图失败: %s", exc)
    return None


def _screenshot_canvas(frame: Any) -> bytes | None:
    """截登录框内二维码 canvas。"""
    try:
        canvas = frame.query_selector("canvas")
        if canvas is None:
            return None
        box = canvas.bounding_box()
        if not box or box["width"] < 100 or box["height"] < 100:
            return None
        png = canvas.screenshot(type="png")
        return png if png else None
    except Exception:
        return None


def _screenshot_loaded_qr(frame: Any) -> bytes | None:
    """只截已 complete 且尺寸足够的二维码节点。"""
    handle = frame.evaluate_handle(
        """() => {
          const canvases = [...document.querySelectorAll('canvas')];
          for (const c of canvases) {
            if ((c.width || c.offsetWidth) >= 100 && (c.height || c.offsetHeight) >= 100) {
              return c;
            }
          }
          let best = null;
          let bestArea = 0;
          for (const img of document.querySelectorAll('img')) {
            if (!img.complete || img.naturalWidth < 80 || img.naturalHeight < 80) continue;
            const r = img.getBoundingClientRect();
            if (r.width < 80 || r.height < 80) continue;
            const ratio = r.width / r.height;
            if (ratio < 0.7 || ratio > 1.4) continue;
            const area = r.width * r.height;
            if (area > bestArea) { bestArea = area; best = img; }
          }
          return best;
        }"""
    )
    try:
        element = handle.as_element()
        if element is None:
            return None
        png = element.screenshot(type="png")
        return png if png else None
    except Exception:
        return None
    finally:
        try:
            handle.dispose()
        except Exception:
            pass


def _screenshot_iframe_qr_panel(page: Any) -> bytes | None:
    """截 iframe 右侧二维码面板（整框比例不对，不能当二维码）。"""
    handle = page.query_selector(f"#{_LOGIN_IFRAME_ID}")
    if handle is None:
        return None
    box = handle.bounding_box()
    if not box or box["width"] < 300 or box["height"] < 200:
        return None
    # 右侧约 40% 为扫码区
    clip = {
        "x": box["x"] + box["width"] * 0.55,
        "y": box["y"] + box["height"] * 0.12,
        "width": box["width"] * 0.40,
        "height": box["height"] * 0.72,
    }
    try:
        return page.screenshot(type="png", clip=clip)
    except Exception:
        return None


def _is_valid_png(data: bytes) -> bool:
    """PNG 魔数 + 最小体积（排除空图/裂图占位）。"""
    return bool(data) and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 500


def _b64_looks_like_qr(encoded: str) -> bool:
    """base64 PNG 是否像可扫二维码。"""
    try:
        raw = base64.b64decode(encoded, validate=False)
    except Exception:
        return False
    return _png_looks_like_qr(raw)


def _png_looks_like_qr(data: bytes) -> bool:
    """近似正方形 + 足够黑白对比（拒空白 / 带大块留白的面板截图）。"""
    if not _is_valid_png(data):
        return False
    from io import BytesIO

    from PIL import Image

    try:
        img = Image.open(BytesIO(data)).convert("L")
    except Exception:
        return False
    width, height = img.size
    if width < 80 or height < 80:
        return False
    ratio = width / height
    if ratio < 0.75 or ratio > 1.35:
        return False
    # 真二维码暗色约 35%~55%；右侧面板含 logo/文案暗色常 <20%
    sample = img.resize((64, 64), Image.Resampling.NEAREST)
    pixels = list(sample.get_flattened_data())
    dark = sum(1 for p in pixels if p < 140)
    frac = dark / max(1, len(pixels))
    return 0.22 <= frac <= 0.62


def _jpeg_to_png(jpeg_bytes: bytes) -> bytes:
    """下载到的二维码若是 JPEG，转 PNG 以匹配前端 data:image/png。"""
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(jpeg_bytes)).convert("RGB")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def login_modal_visible(page: Any) -> bool:
    """登录弹窗是否仍在。"""
    return bool(
        page.evaluate(
            """() => {
              const f = document.querySelector('#alibaba-login-box');
              if (f) {
                const r = f.getBoundingClientRect();
                if (r.width >= 80 && r.height >= 80) return true;
              }
              const t = document.body ? document.body.innerText : '';
              return t.includes('短信登录') || t.includes('使用 1688App') || t.includes('扫码登录');
            }"""
        )
    )


def is_logged_in(page: Any) -> bool:
    """登录成功：出现「我的ak/我的发布」，或登录框已收起且顶栏无「登录」。"""
    return bool(
        page.evaluate(
            """() => {
              const t = document.body ? document.body.innerText : '';
              if (t.includes('我的ak') || t.includes('我的AK') || t.includes('我的发布')) {
                return true;
              }
              if (t.includes('短信登录') || t.includes('使用 1688App') || t.includes('扫码登录')) {
                return false;
              }
              const f = document.querySelector('#alibaba-login-box');
              if (f) {
                const r = f.getBoundingClientRect();
                if (r.width >= 80 && r.height >= 80) return false;
              }
              const nodes = [...document.querySelectorAll('a,button,div,span')];
              return !nodes.some(e => (e.textContent || '').trim() === '登录');
            }"""
        )
    )


def login_completed_after_scan(page: Any) -> bool:
    """手机已确认：登录 iframe 收起，且不再显示短信/扫码文案。"""
    return bool(
        page.evaluate(
            """() => {
              const t = document.body ? document.body.innerText : '';
              if (t.includes('短信登录') || t.includes('使用 1688App') || t.includes('扫码登录')) {
                return false;
              }
              const f = document.querySelector('#alibaba-login-box');
              if (f) {
                const r = f.getBoundingClientRect();
                // iframe 仍占位则未完成
                if (r.width >= 80 && r.height >= 80) return false;
              }
              // 顶栏已不是「登录」，或出现「我的ak」
              if (t.includes('我的ak') || t.includes('我的AK') || t.includes('我的发布')) return true;
              const nodes = [...document.querySelectorAll('a,button,div,span')];
              return !nodes.some(e => (e.textContent || '').trim() === '登录');
            }"""
        )
    )


def looks_scanned(page: Any) -> bool:
    """弹窗文案提示已扫码待确认（主文档 + iframe）。"""
    if page.evaluate(
        """() => {
          const t = document.body ? document.body.innerText : '';
          return /已扫码|确认登录|扫描成功|请在手机/.test(t);
        }"""
    ):
        return True
    frame = find_login_frame(page)
    if frame is None:
        return False
    try:
        text = frame.locator("body").inner_text(timeout=1000)
        return bool(re.search(r"已扫码|确认登录|扫描成功|请在手机", text or ""))
    except Exception:
        return False


def extract_ak_from_page(page: Any, *, timeout_ms: int = 12_000) -> str:
    """点击钥匙 /「我的ak」，从弹层读取 AK 明文。"""
    page.wait_for_timeout(200)
    # 登录刚完成时页面可能还在跳转，短暂等「我的ak」
    for _ in range(10):
        ready = page.evaluate(
            """() => {
              const t = document.body ? document.body.innerText : '';
              return t.includes('我的ak') || t.includes('我的AK') || t.includes('我的发布');
            }"""
        )
        if ready:
            break
        page.wait_for_timeout(200)

    opened = page.evaluate(
        """() => {
          const nodes = [...document.querySelectorAll('a,button,div,span')];
          const mine = nodes.find(e => /我的\\s*ak/i.test((e.textContent || '').trim()));
          if (mine) { mine.click(); return 'clicked-my-ak'; }
          const buttons = [...document.querySelectorAll('button')];
          const iconBtns = buttons.filter(b => {
            const t = (b.textContent || '').trim();
            return t === '' || t.length <= 2;
          });
          const publish = buttons.find(b => (b.textContent || '').includes('发布'));
          if (publish) {
            const all = buttons;
            const idx = all.indexOf(publish);
            for (const cand of [all[idx + 1], all[idx - 1], ...iconBtns]) {
              if (cand) { cand.click(); return 'clicked-near-publish'; }
            }
          }
          if (iconBtns.length) { iconBtns[0].click(); return 'clicked-icon'; }
          const byTitle = buttons.find(b =>
            /key|ak|密钥/i.test(b.getAttribute('title') || b.getAttribute('aria-label') || '')
          );
          if (byTitle) { byTitle.click(); return 'clicked-title'; }
          return '';
        }"""
    )
    if not opened:
        raise RuntimeError("未找到 AK 入口（钥匙或「我的ak」），请确认已登录 clawhub")
    logger.info("已打开 AK 面板 via=%s", opened)
    page.wait_for_timeout(300)

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        raw = page.evaluate(
            """() => {
              for (const el of document.querySelectorAll('input,textarea')) {
                const v = (el.value || '').trim();
                if (v.length >= 40) return v;
              }
              const body = document.body ? document.body.innerText : '';
              const re = /[A-Za-z0-9_\\-=]{40,}/g;
              const m = body.match(re);
              if (m && m.length) {
                return m.sort((a,b) => b.length - a.length)[0];
              }
              return '';
            }"""
        )
        if isinstance(raw, str) and raw.strip():
            candidate = raw.strip()
            ak_id, secret = extract_ak_keys(candidate)
            if ak_id and secret:
                return candidate
        page.evaluate(
            """() => {
              const nodes = [...document.querySelectorAll('button,a,span,div')];
              const copy = nodes.find(e => (e.textContent || '').trim() === '复制');
              if (copy) copy.click();
            }"""
        )
        page.wait_for_timeout(250)

    raise RuntimeError("已登录但未能读取 AK，请在 clawhub「我的ak」确认可见后重试")


def is_plausible_ak(raw: str) -> bool:
    """粗校验 AK 形态。"""
    if not raw or len(raw) < 32:
        return False
    compact = raw.strip()
    ak_id, secret = extract_ak_keys(compact)
    return bool(ak_id and secret)
