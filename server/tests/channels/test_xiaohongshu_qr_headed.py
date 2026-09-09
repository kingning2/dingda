"""小红书有头扫码登录（手动）。

默认跳过；需要真人扫码时：

    cd server
    set XHS_HEADED_LOGIN=1
    .venv\\Scripts\\python.exe -m pytest tests/channels/test_xiaohongshu_qr_headed.py -s -q
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.probe_xiaohongshu_qr_login import run_headed_qr_login  # noqa: E402


@pytest.mark.skipif(
    os.environ.get("XHS_HEADED_LOGIN", "").strip() not in {"1", "true", "yes"},
    reason="设置 XHS_HEADED_LOGIN=1 后才会弹有头浏览器扫码",
)
def test_xiaohongshu_headed_qr_login_reads_nickname() -> None:
    """扫码成功后应得到稳定 user_id 账号，且尽量读到真实昵称。"""
    result = run_headed_qr_login(timeout_s=180, save=True)
    assert result["ok"] is True
    assert str(result["account_id"]).startswith("xhs:")
    assert len(str(result["account_id"])) > len("xhs:") + 12
    assert result["has_cookie"] is True
    assert result["display_name"]
    assert result["display_name"] != "新小红书账号"
