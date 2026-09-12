"""从各平台用户资料 JSON 提取昵称与头像 URL。"""

from __future__ import annotations

from typing import Any

_NAME_KEYS = ("nickname", "nick", "displayName", "display_name", "userName", "user_name")
_AVATAR_KEYS = (
    "avatar",
    "avatarUrl",
    "avatar_url",
    "image",
    "images",
    "headPhoto",
    "head_photo",
    "headPicture",
    "head_picture",
    "userAvatar",
    "user_avatar",
    "portrait",
    "headUrl",
    "head_url",
    "userPhoto",
    "user_photo",
    "icon",
    "photo",
)


def _first_str(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_display_name(data: dict[str, Any]) -> str | None:
    return _first_str(data, _NAME_KEYS)


def extract_avatar_url(data: dict[str, Any]) -> str | None:
    return _first_str(data, _AVATAR_KEYS)


def extract_profile_from_tree(info: dict[str, Any]) -> tuple[str | None, str | None]:
    """在嵌套 userInfo / basicInfo / userPageData 结构中查找昵称与头像。"""
    if not info:
        return None, None

    user_info = info.get("userInfo")
    if isinstance(user_info, dict):
        if user_info.get("guest") is True:
            return None, None
        name = extract_display_name(user_info)
        avatar = extract_avatar_url(user_info)
        if name or avatar:
            return name, avatar

    page_data = info.get("userPageData")
    if isinstance(page_data, dict):
        basic = page_data.get("basicInfo") or page_data.get("basic_info") or {}
        if isinstance(basic, dict):
            name = extract_display_name(basic)
            avatar = extract_avatar_url(basic)
            if name or avatar:
                return name, avatar

    login_info = info.get("login_info")
    if isinstance(login_info, dict):
        name = extract_display_name(login_info)
        avatar = extract_avatar_url(login_info)
        if name or avatar:
            return name, avatar

    return extract_display_name(info), extract_avatar_url(info)
