"""在终端展示二维码（半块字符渲染，逻辑与 xhs-cli auth.py 一致）。"""

from __future__ import annotations

import base64
import io
import sys


def show_qr_in_terminal(qr_base64: str, *, qr_url: str | None = None) -> bool:
    """将二维码渲染到终端。优先用 URL 文本生成矩阵（与 xhs-cli 相同），否则从 PNG 解码。"""
    _ensure_utf8_console()

    text = (qr_url or "").strip()
    if not text and qr_base64:
        text = (_decode_qr_text_from_png_base64(qr_base64) or "").strip()

    if text and _display_qr_text_in_terminal(text):
        return True

    if qr_url:
        _safe_terminal_print(f"QR URL: {qr_url}")
        return False

    _safe_terminal_print("Failed to render QR in terminal.")
    return False


def decode_qr_text_from_png_base64(qr_base64: str) -> str | None:
    """从 PNG base64 解码二维码内容（闲鱼等仅返回图片时使用）。"""
    return _decode_qr_text_from_png_base64(qr_base64)


def _decode_qr_text_from_png_base64(qr_base64: str) -> str | None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    try:
        raw = base64.b64decode(qr_base64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if image is None:
            return None

        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(image)
        if data:
            return data

        ok, decoded, _, _ = detector.detectAndDecodeMulti(image)
        if ok and decoded:
            for item in decoded:
                if item:
                    return item
    except Exception:
        return None
    return None


def _ensure_utf8_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass


def _safe_terminal_print(text: str) -> None:
    if not text:
        return
    try:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        return
    except Exception:
        pass
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _display_qr_text_in_terminal(qr_text: str) -> bool:
    """Render QR text as terminal half-block art (xhs-cli)."""
    try:
        import qrcode
    except ImportError:
        return False

    try:
        qr = qrcode.QRCode(border=0)
        qr.add_data(qr_text)
        qr.make(fit=True)
        rendered = _render_qr_half_blocks(qr.get_matrix())
        if not rendered:
            return False
        _safe_terminal_print(rendered)
        return True
    except Exception:
        return False


def _render_qr_half_blocks(matrix: list[list[bool]]) -> str:
    """Render QR matrix using half-block characters (▀▄█) — copied from xhs-cli."""
    if not matrix:
        return ""

    border = 2
    width = len(matrix[0]) + border * 2
    padded = [[False] * width for _ in range(border)]
    for row in matrix:
        padded.append(([False] * border) + row + ([False] * border))
    padded.extend([[False] * width for _ in range(border)])

    chars = {
        (False, False): " ",
        (True, False): "▀",
        (False, True): "▄",
        (True, True): "█",
    }

    lines = []
    for y in range(0, len(padded), 2):
        top = padded[y]
        bottom = padded[y + 1] if y + 1 < len(padded) else [False] * width
        line = "".join(chars[(top[x], bottom[x])] for x in range(width))
        lines.append(line)
    return "\n".join(lines)
