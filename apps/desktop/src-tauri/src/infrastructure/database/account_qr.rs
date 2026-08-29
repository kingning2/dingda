//! 共享扫码账号派生 — 从 sidecar 导出的 Cookie 构造业务账号（按平台分袋）。
//!
//! 纯逻辑、无 Tauri 类型。1688 站账号由 `platform-ali1688` 自行构造；
//! 本模块只保留闲鱼/兜底构建器（避免共享层依赖具体 Provider）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

use crate::contracts::ChannelCookie;
use crate::domain::account::{
    AccountAutomation, AccountStatus, DeliveryGuard, LoginMethod, ProxyConfig, XianyuAccount,
};
use crate::infrastructure::database::account::{
    cookie_domains_for_log, xianyu_cookie_header, xiaohongshu_cookie_header,
};

/// 从 cookies 构造业务账号（单站，按平台分袋）。
///
/// 闲鱼：`account_id` 取 `unb`；小红书：取 `web_session`（缺失时用 cookie 头哈希兜底，
/// 保证同一平台多次登录各自成独立账号）。
pub fn account_from_cookies(platform: &str, cookies: &[ChannelCookie]) -> XianyuAccount {
    let (account_id, unb, cookie) = if platform == "xiaohongshu" {
        let session = cookies
            .iter()
            .find(|c| c.name == "web_session")
            .map(|c| c.value.clone())
            .unwrap_or_default();
        let header = xiaohongshu_cookie_header(cookies);
        let id = if session.is_empty() {
            format!("xiaohongshu-qr-{}", simple_hash(&header))
        } else {
            session
        };
        (id, String::new(), header)
    } else {
        let unb = cookies
            .iter()
            .find(|cookie| cookie.name == "unb")
            .map(|cookie| cookie.value.clone())
            .unwrap_or_default();
        let id = if unb.is_empty() {
            "xianyu-qr".to_string()
        } else {
            unb.clone()
        };
        (id, unb, xianyu_cookie_header(cookies))
    };

    let domains = cookie_domains_for_log(cookies).join(",");

    tracing::info!(platform, domains, "单站登录态已判定");

    XianyuAccount {
        id: 0,
        owner_id: 1,
        account_id,
        display_name: String::new(),
        avatar_url: String::new(),
        login_id: String::new(),
        login_password: String::new(),
        unb,
        cookie,
        cookie_1688: String::new(),
        platform: platform.to_string(),
        login_method: LoginMethod::Qr,
        status: AccountStatus::Active,
        remark: String::new(),
        pause_duration_minutes: 10,
        last_login_at: Some(now_string()),
        last_refresh_at: None,
        proxy: ProxyConfig::default(),
        automation: AccountAutomation::default(),
        delivery_guard: DeliveryGuard::default(),
    }
}

fn simple_hash(value: &str) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut hasher = DefaultHasher::new();
    value.hash(&mut hasher);
    format!("{:x}", hasher.finish())
}

fn now_string() -> String {
    chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contracts::ChannelCookie;

    fn cookie(name: &str, value: &str, domain: &str) -> ChannelCookie {
        ChannelCookie {
            name: name.to_string(),
            value: value.to_string(),
            domain: domain.to_string(),
            path: "/".to_string(),
            expires: None,
            http_only: None,
            secure: None,
            same_site: None,
        }
    }

    #[test]
    fn xiaohongshu_derives_account_id_from_web_session() {
        let cookies = vec![
            cookie("web_session", "SESS-1", ".xiaohongshu.com"),
            cookie("a1", "A1", ".xiaohongshu.com"),
        ];
        let account = account_from_cookies("xiaohongshu", &cookies);
        assert_eq!(account.platform, "xiaohongshu");
        assert_eq!(account.account_id, "SESS-1");
        assert!(account.cookie.contains("web_session=SESS-1"));
        assert!(account.unb.is_empty());
    }

    #[test]
    fn xiaohongshu_falls_back_to_deterministic_hash_id() {
        let cookies = vec![cookie("a1", "A1", ".xiaohongshu.com")];
        let a = account_from_cookies("xiaohongshu", &cookies);
        let b = account_from_cookies("xiaohongshu", &cookies);
        assert!(a.account_id.starts_with("xiaohongshu-qr-"));
        assert_eq!(a.account_id, b.account_id);
    }

    #[test]
    fn xianyu_still_uses_unb() {
        let cookies = vec![
            cookie("unb", "U1", ".goofish.com"),
            cookie("_m_h5_tk", "xy", ".goofish.com"),
        ];
        let account = account_from_cookies("xianyu", &cookies);
        assert_eq!(account.account_id, "U1");
        assert_eq!(account.unb, "U1");
    }
}
