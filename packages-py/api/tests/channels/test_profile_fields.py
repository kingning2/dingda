"""profile_fields 单元测试。"""

from __future__ import annotations

from channels.profile_fields import extract_avatar_url, extract_profile_from_tree


class TestProfileFields:
    def test_extract_from_basic_info(self) -> None:
        name, avatar = extract_profile_from_tree(
            {
                "userPageData": {
                    "basicInfo": {
                        "nickname": "Alice",
                        "images": "https://img.test/avatar.jpg",
                        "userId": "u1",
                    }
                }
            }
        )
        assert name == "Alice"
        assert avatar == "https://img.test/avatar.jpg"

    def test_extract_from_login_info(self) -> None:
        name, avatar = extract_profile_from_tree(
            {
                "login_info": {
                    "nickname": "小红",
                    "avatar": "https://img.test/xhs.png",
                }
            }
        )
        assert name == "小红"
        assert avatar == "https://img.test/xhs.png"

    def test_extract_xianyu_avatar(self) -> None:
        assert extract_avatar_url({"nick": "店", "portrait": "https://img.test/xy.png"}) == (
            "https://img.test/xy.png"
        )
