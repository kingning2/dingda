"""渠道浏览器任务用的平台配置（登录页 URL、二维码选择器、Cookie 域）。

作者：Xiaoman
创建时间：2026-08-21
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformConfig:
    """单个平台的浏览器任务配置。

    作者：Xiaoman
    创建时间：2026-08-21
    """

    login_entry_url: str
    home_url: str
    qr_selectors: list[str]
    login_cookie_name: str
    cookie_domain_keyword: str
    # 备用登录 Cookie（SSO 中间态判定）：1688 扫码后先落淘宝 `unb`，
    # 补访首页完成 SSO 后才有本站 Cookie。无 SSO 流程的平台留空。
    sso_cookie_name: str | None = None
    sso_cookie_domain_keyword: str | None = None


PLATFORM_CONFIGS: dict[str, PlatformConfig] = {
    "xianyu": PlatformConfig(
        login_entry_url=(
            "https://passport.goofish.com/mini_login.htm"
            "?lang=zh_cn&appName=xianyu&appEntrance=web&styleType=vertical"
            "&isMobile=false&qrCodeFirst=true&notKeepLogin=false"
        ),
        home_url="https://www.goofish.com/",
        qr_selectors=[
            "div.qrcode-img",
            "#qrcode-img",
            "canvas",
            "img.qrcode-img",
        ],
        login_cookie_name="unb",
        cookie_domain_keyword="goofish.com",
    ),
    # 1688：直连 signin 页，QR 由 qrcode/generate API 拦截（见 Ali1688Qrcode）
    "ali1688": PlatformConfig(
        login_entry_url="https://login.1688.com/member/signin.htm?tbpm=1",
        home_url=("https://air.1688.com/app/ctf-page/trade-order-list/buyer-order-list.html"),
        qr_selectors=[
            "canvas",
            "img.qrcode-img",
            "div.qrcode-img",
            "#qrcode-img",
            "img[src*='qrcode']",
            ".login-qrcode-img",
        ],
        login_cookie_name="unb",
        cookie_domain_keyword="1688.com",
        sso_cookie_name="unb",
        sso_cookie_domain_keyword="taobao.com",
    ),
}


def normalize_platform(platform: str | None) -> str:
    """标准化平台标识，默认回退 xianyu；`1688` 视同 `ali1688`。

    作者：Xiaoman
    创建时间：2026-08-21

    参数：
        platform: 原始平台名；空则视为闲鱼。

    返回：
        小写平台标识。
    """
    value = (platform or "xianyu").strip().lower() or "xianyu"
    if value == "1688":
        return "ali1688"
    return value


def get_platform_config(platform: str | None) -> PlatformConfig:
    """获取平台配置；未知平台抛错，避免误用闲鱼选择器。

    作者：Xiaoman
    创建时间：2026-08-21

    参数：
        platform: 平台标识。

    返回：
        对应 [`PlatformConfig`]。

    异常：
        ValueError: 不支持的平台。
    """
    normalized = normalize_platform(platform)
    config = PLATFORM_CONFIGS.get(normalized)
    if config is None:
        supported = ", ".join(sorted(PLATFORM_CONFIGS.keys()))
        raise ValueError(f"不支持的平台: {normalized}（支持: {supported}）")
    return config
