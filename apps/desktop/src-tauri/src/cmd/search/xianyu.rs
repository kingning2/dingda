//! 闲鱼关键词搜索 — Sidecar Camoufox/Chromium + MTOP 拦截。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

use crate::cmd::IpcResponse;
use crate::contracts::contracts::ChannelSidecarSearchRequest;
use crate::core::domain::account::AccountService;
use crate::core::store::cookies::parse_credential;
use crate::core::store::resolve_account_platform;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::State;

use crate::cmd::AccountHandle;
use crate::utils::state::AppState;

/// 闲鱼搜索 IPC 入参。
#[derive(Debug, Deserialize)]
pub struct XianyuSearchRequest {
    pub owner_id: i64,
    pub account_id: String,
    pub keyword: String,
    #[serde(default)]
    pub max_results: Option<i64>,
    /// 有头浏览器（默认 true，便于过滑块）。
    #[serde(default = "default_headed")]
    pub headed: bool,
}

fn default_headed() -> bool {
    true
}

/// 闲鱼搜索 IPC 出参（与 sidecar 响应对齐）。
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct XianyuSearchResponse {
    pub ok: bool,
    pub status: String,
    pub keyword: String,
    pub total: i64,
    pub total_before_filter: i64,
    pub offers: Vec<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub final_url: Option<String>,
    pub detail: String,
}

/// 闲鱼关键词搜索（Camoufox / Chromium）。
#[tauri::command]
pub async fn xianyu_search(
    state: State<'_, AppState>,
    account_handle: State<'_, AccountHandle>,
    request: XianyuSearchRequest,
) -> crate::contracts::DingDaResult<IpcResponse<XianyuSearchResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    let keyword = request.keyword.trim();
    if keyword.is_empty() {
        return Err(crate::contracts::DingDaError::validation(
            "搜索关键词不能为空",
        ));
    }

    let service = AccountService::new(account_handle.store.as_ref());
    let account = service
        .list(request.owner_id)
        .map_err(crate::contracts::DingDaError::wrap)?
        .into_iter()
        .find(|item| item.account_id == request.account_id)
        .ok_or_else(|| crate::contracts::DingDaError::validation("账号不存在"))?;

    let platform = resolve_account_platform(&account.account_id, &account.platform);
    if platform != "xianyu" {
        return Err(crate::contracts::DingDaError::validation(
            "仅支持闲鱼账号搜索",
        ));
    }

    let cookie = account.cookie.trim();
    if cookie.is_empty() {
        return Err(crate::contracts::DingDaError::validation(
            "账号 Cookie 为空，请先扫码登录",
        ));
    }

    let cookies = parse_credential(cookie);
    if cookies.is_empty() {
        return Err(crate::contracts::DingDaError::validation(
            "无法解析账号 Cookie",
        ));
    }

    let max_results = request.max_results.unwrap_or(20).clamp(1, 120);
    let sidecar_request = ChannelSidecarSearchRequest {
        account_id: request.account_id.clone(),
        keyword: keyword.to_string(),
        cookies,
        max_results: Some(max_results),
        headed: Some(request.headed),
        platform: Some("xianyu".to_string()),
        trace_id: Some(format!("xianyu-search-{}", request.account_id)),
    };

    let sidecar = state.lifecycle.client();
    let response: Value = sidecar
        .post_json("/v1/channel/search", &sidecar_request)
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    let offers = response
        .get("offers")
        .cloned()
        .unwrap_or(Value::Array(vec![]));

    Ok(IpcResponse::ok(XianyuSearchResponse {
        ok: response.get("ok").and_then(Value::as_bool).unwrap_or(false),
        status: response
            .get("status")
            .and_then(Value::as_str)
            .unwrap_or("error")
            .to_string(),
        keyword: response
            .get("keyword")
            .and_then(Value::as_str)
            .unwrap_or(keyword)
            .to_string(),
        total: response.get("total").and_then(Value::as_i64).unwrap_or(0),
        total_before_filter: response
            .get("total_before_filter")
            .and_then(Value::as_i64)
            .or_else(|| response.get("totalBeforeFilter").and_then(Value::as_i64))
            .unwrap_or(0),
        offers: offers.as_array().cloned().unwrap_or_default(),
        final_url: response
            .get("final_url")
            .or_else(|| response.get("finalUrl"))
            .and_then(Value::as_str)
            .map(str::to_string),
        detail: response
            .get("detail")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
    }))
}
