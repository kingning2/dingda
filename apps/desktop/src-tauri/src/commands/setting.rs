//! 设置类 IPC — 风控日志 / 配置 / 用户级键值存储。

use crate::commands::IpcResponse;
use crate::domain::risk::{RiskConfig, RiskLogPage, RiskLogQuery, RiskService};
use crate::domain::setting::UserSettingService;
use crate::infrastructure::storage::{InMemoryRiskStore, InMemoryUserSettingStore};
use serde::Deserialize;
use std::sync::Arc;
use tauri::State;

/// 风控服务句柄（setup 时注册到 Tauri 状态）。
pub struct RiskHandle {
    pub store: Arc<InMemoryRiskStore>,
}

/// 日志查询请求。
#[derive(Debug, Deserialize)]
pub struct RiskListRequest {
    pub owner_id: i64,
    pub page: u32,
    pub page_size: u32,
    #[serde(default)]
    pub account_id: String,
    #[serde(default)]
    pub start_date: String,
    #[serde(default)]
    pub end_date: String,
    #[serde(default)]
    pub processing_status: String,
    #[serde(default)]
    pub call_type: String,
    #[serde(default)]
    pub call_user: String,
}

/// 清空日志请求。
#[derive(Debug, Deserialize)]
pub struct RiskClearRequest {
    pub owner_id: i64,
    #[serde(default)]
    pub account_id: String,
}

/// 今日成功率请求。
#[derive(Debug, Deserialize)]
pub struct RiskRateRequest {
    pub owner_id: i64,
    /// yyyy-mm-dd（北京时间当天）。
    pub date: String,
}

/// 保存风控配置请求。
#[derive(Debug, Deserialize)]
pub struct RiskConfigSaveRequest {
    pub owner_id: i64,
    pub config: RiskConfig,
}

/// 分页查询风控日志。
#[tauri::command]
pub fn risk_log_list(
    state: State<'_, RiskHandle>,
    request: RiskListRequest,
) -> crate::contracts::DingDaResult<IpcResponse<RiskLogPage>> {
    let service = RiskService::new(state.store.as_ref());
    let query = RiskLogQuery {
        page: request.page,
        page_size: request.page_size,
        account_id: request.account_id,
        start_date: request.start_date,
        end_date: request.end_date,
        processing_status: request.processing_status,
        call_type: request.call_type,
        call_user: request.call_user,
    };
    let result = service.list(request.owner_id, &query)?;
    Ok(IpcResponse::ok(result))
}

/// 查询指定日期风控处理成功率。
#[tauri::command]
pub fn risk_log_today_rate(
    state: State<'_, RiskHandle>,
    request: RiskRateRequest,
) -> crate::contracts::DingDaResult<IpcResponse<crate::domain::risk::RiskTodaySuccessRate>> {
    let service = RiskService::new(state.store.as_ref());
    let result = service.today_success_rate(request.owner_id, &request.date)?;
    Ok(IpcResponse::ok(result))
}

/// 清空风控日志（可按账号过滤）。
#[tauri::command]
pub fn risk_log_clear(
    state: State<'_, RiskHandle>,
    request: RiskClearRequest,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    let service = RiskService::new(state.store.as_ref());
    service.clear(request.owner_id, &request.account_id)?;
    Ok(IpcResponse::ok(()))
}

/// 清空处理中状态的风控日志。
#[tauri::command]
pub fn risk_log_clear_processing(
    state: State<'_, RiskHandle>,
    owner_id: i64,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    let service = RiskService::new(state.store.as_ref());
    service.clear_processing(owner_id)?;
    Ok(IpcResponse::ok(()))
}

/// 读取风控配置。
#[tauri::command]
pub fn risk_config_get(
    state: State<'_, RiskHandle>,
    owner_id: i64,
) -> crate::contracts::DingDaResult<IpcResponse<RiskConfig>> {
    let service = RiskService::new(state.store.as_ref());
    let result = service.get_config(owner_id)?;
    Ok(IpcResponse::ok(result))
}

/// 保存风控配置。
#[tauri::command]
pub fn risk_config_set(
    state: State<'_, RiskHandle>,
    request: RiskConfigSaveRequest,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    let service = RiskService::new(state.store.as_ref());
    service
        .save_config(request.owner_id, &request.config)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(()))
}

/// 用户设置服务句柄（setup 时注册到 Tauri 状态）。
pub struct UserSettingHandle {
    pub store: Arc<InMemoryUserSettingStore>,
}

/// 单键读取请求。
#[derive(Debug, Deserialize)]
pub struct SettingGetRequest {
    pub owner_id: i64,
    pub key: String,
}

/// 单键写入请求。
#[derive(Debug, Deserialize)]
pub struct SettingSetRequest {
    pub owner_id: i64,
    pub key: String,
    pub value: String,
}

/// 读取单键设置。
#[tauri::command]
pub fn user_setting_get(
    state: State<'_, UserSettingHandle>,
    request: SettingGetRequest,
) -> crate::contracts::DingDaResult<IpcResponse<Option<String>>> {
    let service = UserSettingService::new(state.store.as_ref());
    let result = service.get(request.owner_id, &request.key)?;
    Ok(IpcResponse::ok(result))
}

/// 写入单键设置。
#[tauri::command]
pub fn user_setting_set(
    state: State<'_, UserSettingHandle>,
    request: SettingSetRequest,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    let service = UserSettingService::new(state.store.as_ref());
    service.set(request.owner_id, &request.key, &request.value)?;
    Ok(IpcResponse::ok(()))
}
