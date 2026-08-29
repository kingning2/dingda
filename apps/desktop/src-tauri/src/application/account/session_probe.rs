//! 账号登录态探活 — 1688 浏览器探针；闲鱼 HTTP 刷新；小红书签名 `/user/me`。

use crate::contracts::ChannelSidecarLoginProbeRequest;
use crate::domain::account::{AccountService, AccountStore, AccountUpdate};
use crate::infrastructure::database::cookies::parse_credential;
use crate::infrastructure::database::resolve_account_platform;
use crate::infrastructure::database::stores::InMemoryAccountStore;
use crate::infrastructure::sidecar::channel_login;
use crate::infrastructure::sidecar::SidecarLifecycle;
use serde::Serialize;
use std::sync::Arc;

/// 启动探活完成后推送给前端的 Tauri 事件 topic。
pub const ACCOUNTS_SESSION_PROBED_TOPIC: &str = "dingda/accounts-session-probed";

/// 单账号探活结果。
#[derive(Debug, Clone, Serialize)]
pub struct AccountSessionProbeItem {
    pub account_id: String,
    pub online: bool,
}

/// 启动批量探活完成事件载荷。
#[derive(Debug, Clone, Serialize)]
pub struct AccountsSessionProbedPayload {
    pub probes: Vec<AccountSessionProbeItem>,
}

/// 探测单个账号登录态；闲鱼成功时持久化刷新后的 Cookie。
pub async fn probe_account_session(
    store: &InMemoryAccountStore,
    lifecycle: &SidecarLifecycle,
    owner_id: i64,
    account_id: &str,
) -> bool {
    let account = match store.get_account(owner_id, account_id) {
        Ok(Some(account)) => account,
        Ok(None) => {
            info!(
                target: "dingda.platform.login_probe",
                account_id,
                reason = "not_found",
                "账号登录探针跳过"
            );
            return false;
        }
        Err(error) => {
            warn!(
                target: "dingda.platform.login_probe",
                account_id,
                %error,
                "读取账号失败，登录探针跳过"
            );
            return false;
        }
    };

    let platform = resolve_account_platform(&account.account_id, &account.platform);

    info!(
        target: "dingda.platform.login_probe",
        account_id = %account_id,
        platform,
        stored_platform = %account.platform,
        has_cookie = account.has_cookie(),
        unb = %account.unb,
        "账号登录探针开始"
    );

    if !account.has_cookie() {
        info!(
            target: "dingda.platform.login_probe",
            account_id = %account_id,
            reason = "empty_cookie",
            "账号登录探针跳过"
        );
        return false;
    }

    let online = match platform {
        "ali1688" => probe_ali1688(lifecycle, account_id, &account.cookie).await,
        "xianyu" | "xiaohongshu" => {
            probe_http_session(
                store,
                lifecycle,
                owner_id,
                account_id,
                platform,
                &account.cookie,
            )
            .await
        }
        _ => false,
    };

    info!(
        target: "dingda.platform.login_probe",
        account_id = %account_id,
        platform,
        online,
        "账号登录探针完成"
    );
    online
}

/// 启动时批量探活：闲鱼先轮换 Token，其余平台直接探活。
pub async fn probe_all_accounts_on_startup(
    store: Arc<InMemoryAccountStore>,
    lifecycle: Arc<SidecarLifecycle>,
    owner_id: i64,
) -> AccountsSessionProbedPayload {
    let service = AccountService::new(store.as_ref());
    let accounts = service.list(owner_id).unwrap_or_default();
    let with_cookie: Vec<_> = accounts
        .into_iter()
        .filter(|account| account.has_cookie())
        .collect();

    let mut xianyu = Vec::new();
    let mut others = Vec::new();
    for account in with_cookie {
        let platform = resolve_account_platform(&account.account_id, &account.platform);
        if platform == "xianyu" {
            xianyu.push(account);
        } else {
            others.push(account);
        }
    }

    let mut probes = Vec::with_capacity(xianyu.len() + others.len());
    for account in xianyu {
        let online = probe_account_session(
            store.as_ref(),
            lifecycle.as_ref(),
            owner_id,
            &account.account_id,
        )
        .await;
        probes.push(AccountSessionProbeItem {
            account_id: account.account_id,
            online,
        });
    }
    for account in others {
        let online = probe_account_session(
            store.as_ref(),
            lifecycle.as_ref(),
            owner_id,
            &account.account_id,
        )
        .await;
        probes.push(AccountSessionProbeItem {
            account_id: account.account_id,
            online,
        });
    }

    AccountsSessionProbedPayload { probes }
}

async fn probe_ali1688(lifecycle: &SidecarLifecycle, account_id: &str, cookie: &str) -> bool {
    let cookies = parse_credential(cookie);
    if cookies.is_empty() {
        info!(
            target: "dingda.platform.login_probe",
            account_id = %account_id,
            reason = "unparseable_cookie",
            "1688 登录探针跳过"
        );
        return false;
    }

    let sidecar_request = ChannelSidecarLoginProbeRequest {
        account_id: account_id.to_string(),
        cookies,
        headed: Some(false),
        platform: Some("ali1688".to_string()),
        trace_id: Some(format!("ali1688-login-probe-{account_id}")),
    };

    match channel_login::login_probe(lifecycle.client(), sidecar_request).await {
        Ok(response) => {
            info!(
                target: "dingda.platform.ali1688.login_probe",
                account_id = %account_id,
                online = response.online,
                status = %response.status,
                detail = response.detail.as_deref().unwrap_or(""),
                "1688 Playwright 登录探针完成"
            );
            response.ok && response.online
        }
        Err(error) => {
            info!(
                target: "dingda.platform.ali1688.login_probe",
                account_id = %account_id,
                %error,
                "1688 Playwright 登录探针失败，视为离线"
            );
            false
        }
    }
}

async fn probe_http_session(
    store: &InMemoryAccountStore,
    lifecycle: &SidecarLifecycle,
    owner_id: i64,
    account_id: &str,
    platform: &str,
    cookie: &str,
) -> bool {
    let cookies = parse_credential(cookie);
    if cookies.is_empty() {
        info!(
            target: "dingda.platform.login_probe",
            account_id = %account_id,
            platform,
            reason = "unparseable_cookie",
            "HTTP 会话刷新跳过"
        );
        return false;
    }

    if lifecycle.ensure_running().await.is_err() {
        info!(
            target: "dingda.platform.login_probe",
            account_id = %account_id,
            platform,
            reason = "sidecar_unavailable",
            "HTTP 会话刷新跳过"
        );
        return false;
    }

    let sidecar_request = ChannelSidecarLoginProbeRequest {
        account_id: account_id.to_string(),
        cookies,
        headed: None,
        platform: Some(platform.to_string()),
        trace_id: Some(format!("{platform}-session-refresh-{account_id}")),
    };

    match channel_login::login_probe(lifecycle.client(), sidecar_request).await {
        Ok(response) => {
            let online = response.ok && response.online;
            if online {
                if let Some(renewed) = response.cookies.clone() {
                    if let Ok(credential) = serde_json::to_string(&renewed) {
                        let service = AccountService::new(store);
                        if let Err(error) = service.update(
                            owner_id,
                            account_id,
                            &AccountUpdate {
                                cookie: Some(credential),
                                ..Default::default()
                            },
                        ) {
                            warn!(
                                target: "dingda.platform.login_probe",
                                account_id = %account_id,
                                platform,
                                %error,
                                "探活后持久化 Cookie 失败"
                            );
                        }
                    }
                }
            }
            info!(
                target: "dingda.platform.login_probe",
                account_id = %account_id,
                platform,
                online,
                status = %response.status,
                detail = response.detail.as_deref().unwrap_or(""),
                "HTTP 会话刷新完成"
            );
            online
        }
        Err(error) => {
            info!(
                target: "dingda.platform.login_probe",
                account_id = %account_id,
                platform,
                %error,
                "HTTP 会话刷新失败，视为离线"
            );
            false
        }
    }
}
