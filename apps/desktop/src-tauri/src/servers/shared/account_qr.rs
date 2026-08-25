//! 共享扫码账号派生 — 从 sidecar 导出的 Cookie 构造业务账号（按平台分袋）。
//!
//! 纯逻辑、无 Tauri 类型。1688 站账号由 `platform-ali1688` 自行构造；
//! 本模块只保留闲鱼/兜底构建器（避免共享层依赖具体 Provider）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

use crate::contracts::contracts::ChannelCookie;
use crate::servers::domain::account::{
    AccountAutomation, AccountStatus, DeliveryGuard, LoginMethod, ProxyConfig, XianyuAccount,
};
use crate::servers::shared::account::{cookie_domains_for_log, xianyu_cookie_header};

/// 从 cookies 构造业务账号（单站）。
pub fn account_from_cookies(platform: &str, cookies: &[ChannelCookie]) -> XianyuAccount {
    let unb = cookies
        .iter()
        .find(|cookie| cookie.name == "unb")
        .map(|cookie| cookie.value.clone())
        .unwrap_or_default();

    let cookie = xianyu_cookie_header(cookies);
    let account_id = if unb.is_empty() {
        "xianyu-qr".to_string()
    } else {
        unb.clone()
    };
    let domains = cookie_domains_for_log(cookies).join(",");

    tracing::info!(platform = "xianyu", domains, "单站登录态已判定");

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

fn now_string() -> String {
    chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string()
}
