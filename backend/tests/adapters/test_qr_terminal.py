"""终端二维码渲染测试（与 xhs-cli tests/test_auth.py 对齐）。"""

import base64
import io

import qrcode

from src.adapters.channel.qr_terminal import (
    _decode_qr_text_from_png_base64,
    _display_qr_text_in_terminal,
    _render_qr_half_blocks,
    show_qr_in_terminal,
)


class TestQrHalfBlockRender:
    def test_empty_matrix(self) -> None:
        assert _render_qr_half_blocks([]) == ""

    def test_block_character_mapping(self) -> None:
        matrix = [
            [True, False],
            [True, False],
        ]
        rendered = _render_qr_half_blocks(matrix)
        assert "█" in rendered

    def test_half_block_top_and_bottom(self) -> None:
        top_only = [[True], [False]]
        bottom_only = [[False], [True]]
        assert "▀" in _render_qr_half_blocks(top_only)
        assert "▄" in _render_qr_half_blocks(bottom_only)


class TestQrTerminalFlow:
    def test_decode_png_roundtrip(self) -> None:
        payload = "https://example.com/login?token=abc123"
        qr = qrcode.QRCode(border=2, box_size=6)
        qr.add_data(payload)
        qr.make(fit=True)
        buffer = io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
        png_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        decoded = _decode_qr_text_from_png_base64(png_b64)
        assert decoded == payload

    def test_show_qr_from_png_decodes_then_renders(self, capsys) -> None:
        payload = "https://passport.example.com/qr?code=xyz"
        qr = qrcode.QRCode(border=2, box_size=6)
        qr.add_data(payload)
        qr.make(fit=True)
        buffer = io.BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
        png_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        assert show_qr_in_terminal(png_b64) is True
        out = capsys.readouterr().out
        assert "█" in out or "▀" in out or "▄" in out

    def test_display_qr_text_matches_xhs_cli(self, capsys) -> None:
        assert _display_qr_text_in_terminal("hello-qr") is True
        out = capsys.readouterr().out
        assert "█" in out or "▀" in out
