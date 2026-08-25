//! 闲鱼监控 IPC — 任务 CRUD、手动运行、AI 生成关键词、结果列表。

use crate::contracts::DingDaResult;
use crate::core::domain::monitor::{
    ensure_next_run_on_enable, pause_schedule, reset_and_pause_schedule_for_manual_run,
    resume_schedule, MonitorResult, MonitorRun, MonitorService, MonitorStats, MonitorTask,
};
use crate::core::store::{
    InMemoryMonitorResultStore, InMemoryMonitorRunStore, InMemoryMonitorTaskStore,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::State;
use uuid::Uuid;

use crate::cmd::IpcResponse;
use crate::config::ConfigStore;
use crate::feat::xianyu::monitor::ai::{
    build_keyword_prompt, generate_keywords, AiFailoverContext,
};
use crate::feat::xianyu::monitor::{MonitorEngine, MonitorRunSummary};

pub struct MonitorHandle {
    pub tasks: Arc<InMemoryMonitorTaskStore>,
    pub results: Arc<InMemoryMonitorResultStore>,
    pub runs: Arc<InMemoryMonitorRunStore>,
    pub engine: Arc<MonitorEngine>,
}

#[derive(Debug, Deserialize)]
pub struct MonitorTaskUpsertRequest {
    pub owner_id: i64,
    pub id: Option<String>,
    pub name: String,
    pub intent: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    pub account_id: String,
    #[serde(default)]
    pub ai_account_id: String,
    #[serde(default = "default_ai_failover_enabled")]
    pub ai_failover_enabled: bool,
    #[serde(default)]
    pub ai_account_order: Vec<String>,
    #[serde(default = "default_interval")]
    pub interval_minutes: u32,
    #[serde(default = "default_enabled")]
    pub enabled: bool,
    pub ai_criteria: String,
    #[serde(default = "default_max_results")]
    pub max_results: u32,
    #[serde(default = "default_headed")]
    pub headed: bool,
}

fn default_interval() -> u32 {
    5
}
fn default_enabled() -> bool {
    true
}
fn default_max_results() -> u32 {
    20
}
fn default_headed() -> bool {
    false
}
fn default_ai_failover_enabled() -> bool {
    true
}

#[derive(Debug, Deserialize)]
pub struct MonitorTaskIdRequest {
    pub owner_id: i64,
    pub task_id: String,
}

#[derive(Debug, Deserialize)]
pub struct MonitorRunIdRequest {
    pub owner_id: i64,
    pub run_id: String,
}

#[derive(Debug, Deserialize)]
pub struct MonitorGenerateKeywordsRequest {
    pub owner_id: i64,
    pub intent: String,
    pub ai_criteria: String,
    #[serde(default)]
    pub ai_account_id: String,
    #[serde(default = "default_ai_failover_enabled")]
    pub ai_failover_enabled: bool,
    #[serde(default)]
    pub ai_account_order: Vec<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MonitorGenerateKeywordsResponse {
    pub keywords: Vec<String>,
}

fn service(handle: &MonitorHandle) -> MonitorService<'_> {
    MonitorService::new(
        handle.tasks.as_ref(),
        handle.results.as_ref(),
        handle.runs.as_ref(),
    )
}

fn sanitize_ai_account_order(order: &[String], primary: &str) -> Vec<String> {
    let primary = primary.trim();
    let mut seen = std::collections::HashSet::new();
    order
        .iter()
        .map(|item| item.trim())
        .filter(|item| !item.is_empty() && *item != primary && seen.insert(item.to_string()))
        .map(str::to_string)
        .collect()
}

#[tauri::command]
pub async fn monitor_task_list(
    handle: State<'_, MonitorHandle>,
    owner_id: i64,
) -> DingDaResult<IpcResponse<Vec<MonitorTask>>> {
    Ok(IpcResponse::ok(service(&handle).list_tasks(owner_id)?))
}

#[tauri::command]
pub async fn monitor_task_save(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskUpsertRequest,
) -> DingDaResult<IpcResponse<MonitorTask>> {
    let now = Utc::now().to_rfc3339();
    let id = request
        .id
        .clone()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    let existing = service(&handle).get_task(request.owner_id, &id)?;
    let mut task = MonitorTask {
        id,
        owner_id: request.owner_id,
        name: request.name.trim().to_string(),
        intent: request.intent.trim().to_string(),
        keywords: request.keywords,
        account_id: request.account_id,
        ai_account_id: request.ai_account_id.trim().to_string(),
        ai_failover_enabled: request.ai_failover_enabled,
        ai_account_order: sanitize_ai_account_order(
            &request.ai_account_order,
            &request.ai_account_id,
        ),
        interval_minutes: request.interval_minutes.max(1),
        enabled: request.enabled,
        ai_criteria: request.ai_criteria.trim().to_string(),
        max_results: request.max_results.clamp(1, 120),
        headed: request.headed,
        is_running: existing
            .as_ref()
            .map(|item| item.is_running)
            .unwrap_or(false),
        last_run_at: existing.as_ref().and_then(|item| item.last_run_at.clone()),
        last_error: existing.as_ref().and_then(|item| item.last_error.clone()),
        schedule_paused: existing
            .as_ref()
            .map(|item| item.schedule_paused)
            .unwrap_or(false),
        schedule_remaining_secs: existing
            .as_ref()
            .and_then(|item| item.schedule_remaining_secs),
        next_run_at: existing.as_ref().and_then(|item| item.next_run_at.clone()),
        created_at: existing
            .as_ref()
            .map(|item| item.created_at.clone())
            .unwrap_or_else(|| now.clone()),
        updated_at: now,
    };
    if task.name.is_empty() || task.intent.is_empty() || task.ai_criteria.is_empty() {
        return Err(crate::contracts::DingDaError::validation(
            "名称、意图与 AI 标准不能为空",
        ));
    }
    if task.ai_account_id.is_empty() {
        return Err(crate::contracts::DingDaError::validation("请选择 AI 账号"));
    }
    let now_dt = Utc::now();
    if !task.enabled {
        task.schedule_paused = false;
        task.schedule_remaining_secs = None;
        task.next_run_at = None;
    } else if !task.schedule_paused {
        ensure_next_run_on_enable(&mut task, now_dt);
    }
    service(&handle).save_task(&task)?;
    Ok(IpcResponse::ok(task))
}

#[tauri::command]
pub async fn monitor_task_pause_schedule(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskIdRequest,
) -> DingDaResult<IpcResponse<MonitorTask>> {
    let mut task = service(&handle)
        .get_task(request.owner_id, &request.task_id)?
        .ok_or_else(|| crate::contracts::DingDaError::validation("监控任务不存在"))?;
    if !task.enabled {
        return Err(crate::contracts::DingDaError::validation("未启用定时爬取"));
    }
    pause_schedule(&mut task, Utc::now());
    service(&handle).save_task(&task)?;
    Ok(IpcResponse::ok(task))
}

#[tauri::command]
pub async fn monitor_task_resume_schedule(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskIdRequest,
) -> DingDaResult<IpcResponse<MonitorTask>> {
    let mut task = service(&handle)
        .get_task(request.owner_id, &request.task_id)?
        .ok_or_else(|| crate::contracts::DingDaError::validation("监控任务不存在"))?;
    if !task.enabled {
        return Err(crate::contracts::DingDaError::validation("未启用定时爬取"));
    }
    resume_schedule(&mut task, Utc::now());
    service(&handle).save_task(&task)?;
    Ok(IpcResponse::ok(task))
}

#[tauri::command]
pub async fn monitor_task_delete(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskIdRequest,
) -> DingDaResult<IpcResponse<()>> {
    service(&handle).delete_task(request.owner_id, &request.task_id)?;
    Ok(IpcResponse::ok(()))
}

#[tauri::command]
pub async fn monitor_task_run(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskIdRequest,
) -> DingDaResult<IpcResponse<MonitorRunSummary>> {
    let mut task = service(&handle)
        .get_task(request.owner_id, &request.task_id)?
        .ok_or_else(|| crate::contracts::DingDaError::validation("监控任务不存在"))?;
    reset_and_pause_schedule_for_manual_run(&mut task, Utc::now());
    service(&handle).save_task(&task)?;
    let summary = handle
        .engine
        .run_task(request.owner_id, &request.task_id)
        .await?;
    Ok(IpcResponse::ok(summary))
}

#[tauri::command]
pub async fn monitor_result_list(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskIdRequest,
) -> DingDaResult<IpcResponse<Vec<MonitorResult>>> {
    Ok(IpcResponse::ok(
        service(&handle).list_results(request.owner_id, &request.task_id)?,
    ))
}

#[tauri::command]
pub async fn monitor_run_list(
    handle: State<'_, MonitorHandle>,
    request: MonitorTaskIdRequest,
) -> DingDaResult<IpcResponse<Vec<MonitorRun>>> {
    Ok(IpcResponse::ok(
        service(&handle).list_runs(request.owner_id, &request.task_id)?,
    ))
}

#[tauri::command]
pub async fn monitor_run_get(
    handle: State<'_, MonitorHandle>,
    request: MonitorRunIdRequest,
) -> DingDaResult<IpcResponse<Option<MonitorRun>>> {
    Ok(IpcResponse::ok(
        service(&handle).get_run(request.owner_id, &request.run_id)?,
    ))
}

#[tauri::command]
pub async fn monitor_stats(
    handle: State<'_, MonitorHandle>,
    owner_id: i64,
) -> DingDaResult<IpcResponse<MonitorStats>> {
    Ok(IpcResponse::ok(service(&handle).stats(owner_id)?))
}

#[tauri::command]
pub async fn monitor_generate_keywords(
    handle: State<'_, MonitorHandle>,
    config_store: State<'_, Arc<ConfigStore>>,
    request: MonitorGenerateKeywordsRequest,
) -> DingDaResult<IpcResponse<MonitorGenerateKeywordsResponse>> {
    let _ = request.owner_id;
    let config = config_store
        .ai_get()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;
    let mut failover = AiFailoverContext::new(
        &request.ai_account_id,
        request.ai_failover_enabled,
        sanitize_ai_account_order(&request.ai_account_order, &request.ai_account_id),
    );
    let prompt = build_keyword_prompt(&request.intent, &request.ai_criteria);
    let generated = generate_keywords(
        handle.engine.sidecar.as_ref(),
        &config,
        &mut failover,
        &prompt,
    )
    .await
    .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(MonitorGenerateKeywordsResponse {
        keywords: generated.keywords,
    }))
}
