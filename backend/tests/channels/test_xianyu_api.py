"""闲鱼扫码 cookie 判定（无浏览器）。"""

from __future__ import annotations

from src.channels.xianyu import api


def _cookies(**pairs: str) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in pairs.items()]


class TestXianyuCookieDetection:
    def test_baseline_guest_does_not_complete(self) -> None:
        baseline = {"_m_h5_tk": "guest_token"}
        guest = _cookies(_m_h5_tk="guest_token")
        assert api.has_login_completed(guest, baseline) is False
        assert api.has_scanned_cookies(guest, baseline) is False

    def test_stale_session_not_counted(self) -> None:
        baseline = {
            "_m_h5_tk": "t",
            "unb": "u1",
            "cookie2": "c1",
        }
        same = _cookies(_m_h5_tk="t", unb="u1", cookie2="c1")
        assert api.has_login_completed(same, baseline) is False

    def test_scanned_when_unb_arrives(self) -> None:
        baseline = {"_m_h5_tk": "guest"}
        scanned = _cookies(_m_h5_tk="guest", unb="new_user")
        assert api.has_scanned_cookies(scanned, baseline) is True
        assert api.has_login_completed(scanned, baseline) is False

    def test_success_when_session_cookies_new(self) -> None:
        baseline = {"_m_h5_tk": "guest"}
        logged_in = _cookies(_m_h5_tk="fresh", unb="u1", cookie2="c1")
        assert api.has_login_completed(logged_in, baseline) is True
        assert api.has_scanned_cookies(logged_in, baseline) is False

    def test_all_cookies_present_after_scan_is_detectable(self) -> None:
        baseline = {"_m_h5_tk": "guest", "cookie2": "early"}
        confirmed = _cookies(_m_h5_tk="guest", unb="u1", cookie2="early")
        assert api.has_login_completed(confirmed, baseline) is False
        assert api.has_all_login_cookies(confirmed) is True
