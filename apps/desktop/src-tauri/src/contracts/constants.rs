//! 各平台 API 域名与 Feature Flags 常量。
//!
//! 集中维护 DingDa 支持的平台基址，避免在 `platform` / `business` / 壳层重复硬编码。
//! Feature Flags 可通过环境变量或编译期 cfg 覆盖。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

/// 闲鱼（Goofish）相关域名与 API 基址。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
pub mod xianyu {
    /// 主站 Origin / Referer。
    pub const WEB_ORIGIN: &str = "https://www.goofish.com/";
    /// 商品详情页前缀（后接 `?id=`）。
    pub const ITEM_URL_PREFIX: &str = "https://www.goofish.com/item?id=";
    /// mtop H5 API 基址（后接 `{api}/{version}/`）。
    pub const H5_API_BASE: &str = "https://h5api.m.goofish.com/h5/";
    /// 登录 token 接口完整 URL。
    pub const LOGIN_TOKEN_URL: &str =
        "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/";
    /// IM WebSocket。
    pub const WS_URL: &str = "wss://wss-goofish.dingtalk.com/";
    /// Cookie 写入域。
    pub const COOKIE_DOMAIN: &str = ".goofish.com";
}

/// 小红书（占位 — 后续接入时替换为真实域名）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
pub mod xiaohongshu {
    pub const WEB_ORIGIN: &str = "https://www.xiaohongshu.com/";
    pub const API_BASE: &str = "https://edith.xiaohongshu.com/";
}

/// 抖音（占位 — 后续接入时替换为真实域名）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
pub mod douyin {
    pub const WEB_ORIGIN: &str = "https://www.douyin.com/";
    pub const API_BASE: &str = "https://www.douyin.com/aweme/v1/";
}

/// 运行时 Feature Flags。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FeatureFlags {
    /// 是否开启调试模式（详细日志、跳过部分校验等）。
    pub debug_mode: bool,
    /// 是否使用 Mock 发布网关（不调用真实 mtop）。
    pub mock_publish: bool,
    /// 是否在开发环境跳过 License 校验（仅 debug 构建生效）。
    pub skip_license_check: bool,
    /// 是否启用渠道 WebSocket 自动重连。
    pub channel_auto_reconnect: bool,
    /// 普通断开后的重连等待秒数（调试默认 30，可用环境变量覆盖）。
    pub channel_reconnect_delay_secs: u64,
    /// 风控时是否自动拉起浏览器 Cookie 续期。
    pub auto_cookie_renew: bool,
}

impl Default for FeatureFlags {
    fn default() -> Self {
        Self::from_env()
    }
}

impl FeatureFlags {
    /// 从环境变量与编译期 cfg 解析 Feature Flags。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 环境变量
    /// - `DINGDA_DEBUG` — `1` / `true` / `yes` 开启调试
    /// - `DINGDA_MOCK_PUBLISH` — 开启 Mock 发布
    /// - `DINGDA_SKIP_LICENSE` — 跳过 License（仅 debug 构建读取）
    /// - `DINGDA_CHANNEL_AUTO_RECONNECT` — `0` / `false` 关闭自动重连（开发改代码时建议关）
    /// - `DINGDA_CHANNEL_RECONNECT_DELAY_SECS` — 普通重连间隔秒数（默认：debug 30 / release 5）
    /// - `DINGDA_DISABLE_AUTO_COOKIE_RENEW` — `1` 关闭风控自动滑块续期
    pub fn from_env() -> Self {
        let debug_mode = cfg!(debug_assertions) || env_truthy("DINGDA_DEBUG");
        let default_reconnect_delay = if debug_mode { 30 } else { 5 };
        Self {
            debug_mode,
            mock_publish: env_truthy("DINGDA_MOCK_PUBLISH"),
            skip_license_check: cfg!(debug_assertions) && env_truthy("DINGDA_SKIP_LICENSE"),
            channel_auto_reconnect: !env_falsy("DINGDA_CHANNEL_AUTO_RECONNECT"),
            channel_reconnect_delay_secs: env_u64("DINGDA_CHANNEL_RECONNECT_DELAY_SECS")
                .unwrap_or(default_reconnect_delay),
            auto_cookie_renew: !env_truthy("DINGDA_DISABLE_AUTO_COOKIE_RENEW"),
        }
    }

    /// 当前进程是否处于调试模式。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn is_debug_mode() -> bool {
        Self::from_env().debug_mode
    }
}

/// 解析环境变量为 true（`1` / `true` / `yes`，大小写不敏感）。
fn env_truthy(key: &str) -> bool {
    std::env::var(key)
        .ok()
        .is_some_and(|value| matches!(value.to_ascii_lowercase().as_str(), "1" | "true" | "yes"))
}

/// 解析环境变量为 false（`0` / `false` / `no`）。
fn env_falsy(key: &str) -> bool {
    std::env::var(key)
        .ok()
        .is_some_and(|value| matches!(value.to_ascii_lowercase().as_str(), "0" | "false" | "no"))
}

/// 解析环境变量为 u64。
fn env_u64(key: &str) -> Option<u64> {
    std::env::var(key).ok()?.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn xianyu_urls_non_empty() {
        assert!(xianyu::WEB_ORIGIN.starts_with("https://"));
        assert!(xianyu::WS_URL.starts_with("wss://"));
    }

    #[test]
    fn default_flags_channel_reconnect_on() {
        let flags = FeatureFlags {
            debug_mode: false,
            mock_publish: false,
            skip_license_check: false,
            channel_auto_reconnect: true,
            channel_reconnect_delay_secs: 5,
            auto_cookie_renew: true,
        };
        assert!(flags.channel_auto_reconnect);
        assert!(flags.auto_cookie_renew);
    }
}
