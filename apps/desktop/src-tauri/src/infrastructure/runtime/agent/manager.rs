//! Agent Runtime 管理 — 生命周期 + 可控 graph run（pause/seek/failover/网络探活）。

use std::sync::{Arc, RwLock};
use std::time::Duration;

use chrono::Utc;
use uuid::Uuid;

use crate::config::ConfigStore;
use crate::contracts::contracts::{
    AgentSidecarNodeModel, AgentSidecarRunCancelRequest, AgentSidecarRunControlRequest,
    AgentSidecarRunStartRequest, AgentSidecarRunStatusRequest, AiIpcConfigResponse,
};
use crate::contracts::events::{emit, AgentProgressEvent, AppEvent, EventSink};
use crate::infrastructure::runtime::agent::sidecar::agent_run;
use crate::infrastructure::runtime::python::client::SidecarClient;
use crate::infrastructure::runtime::RUNTIME_TARGET;

use super::lifecycle::AgentLifecycle;
use super::models::{build_node_models, failover_account_ids, resolve_account};
use super::state::AgentState;
use super::store::{AgentRunRecord, AgentRunStore, AgentStepRecord};

/// Agent Runtime 管理器。
pub struct AgentRuntime {
    lifecycle: AgentLifecycle,
    client: SidecarClient,
    event_sink: RwLock<Option<Arc<dyn EventSink>>>,
    config: RwLock<Option<Arc<ConfigStore>>>,
    store: RwLock<Option<Arc<AgentRunStore>>>,
    active_run_id: RwLock<Option<String>>,
    /// 当前 run 的 failover 游标（account id 列表）。
    failover_cursor: RwLock<Vec<String>>,
    network_wait_cancel: RwLock<Option<tokio::sync::watch::Sender<bool>>>,
}

impl AgentRuntime {
    /// 组装管理器；`client` 指向 sidecar。
    #[allow(clippy::new_without_default)]
    pub fn new(client: SidecarClient) -> Self {
        Self {
            lifecycle: AgentLifecycle::default(),
            client,
            event_sink: RwLock::new(None),
            config: RwLock::new(None),
            store: RwLock::new(None),
            active_run_id: RwLock::new(None),
            failover_cursor: RwLock::new(Vec::new()),
            network_wait_cancel: RwLock::new(None),
        }
    }

    /// 注入事件 / 配置 / 落库依赖（setup 阶段调用）。
    pub fn configure(
        &self,
        event_sink: Arc<dyn EventSink>,
        config: Arc<ConfigStore>,
        store: Arc<AgentRunStore>,
    ) {
        *self.event_sink.write().expect("agent sink") = Some(event_sink);
        *self.config.write().expect("agent config") = Some(config);
        // 冷启动：孤儿 run → interrupted
        if let Ok(ids) = store.mark_orphans_interrupted() {
            for id in ids {
                info!(target: RUNTIME_TARGET, run_id = %id, "[runtime] agent.run.interrupted");
            }
        }
        *self.store.write().expect("agent store") = Some(store);
    }

    pub fn state(&self) -> AgentState {
        self.lifecycle.state()
    }

    /// 探活 sidecar agent。
    #[macros::runtime(agent, start = Starting, ok = Ready, err = Failed)]
    pub async fn start(&self) -> Result<(), String> {
        match self
            .client
            .post_json::<serde_json::Value, serde_json::Value>(
                "/v1/agent/ping",
                &serde_json::json!({}),
            )
            .await
        {
            Ok(_) => Ok(()),
            Err(error) => {
                warn!(target: RUNTIME_TARGET, %error, "[runtime] agent.ping.failed");
                Err(error.to_string())
            }
        }
    }

    #[macros::runtime(agent, start = Stopping, ok = Stopped)]
    pub fn stop(&self) {}

    pub async fn restart(&self) {
        self.stop();
        let _ = self.start().await;
    }

    /// 启动比价图可控 run。
    pub async fn start_run(
        &self,
        user: String,
        system: Option<String>,
        resume_from_run_id: Option<String>,
        resume_node: Option<String>,
    ) -> Result<AgentRunRecord, String> {
        let config = self.ai_config().await?;
        let graph = config.graph_models.as_ref();
        let (node_models, default_model) = build_node_models(&config, graph)?;
        let (failover_enabled, failover_ids) = failover_account_ids(graph);
        let mut cursor = Vec::new();
        if failover_enabled {
            cursor = failover_ids;
            for m in &node_models {
                if let Some(id) = &m.account_id {
                    if !cursor.iter().any(|x| x == id) {
                        cursor.push(id.clone());
                    }
                }
            }
        }
        *self.failover_cursor.write().expect("failover") = cursor;

        let run_id = Uuid::new_v4().to_string();
        let now = Utc::now().timestamp_millis();
        let mut resume_state_json = None;
        let mut seek_node = resume_node;
        let mut inherited_steps: Vec<AgentStepRecord> = Vec::new();
        if let Some(from) = resume_from_run_id.as_ref() {
            if let Some(prev) = self.store_get(from) {
                inherited_steps = prev.steps.clone();
                if let Some(last) = prev.steps.iter().rev().find(|s| s.status == "done") {
                    resume_state_json = last.state_before_json.clone();
                    // resume from next node after last done — or seek failed node
                    if seek_node.is_none() {
                        seek_node = prev.failed_node.clone().or_else(|| {
                            // next after last done
                            Some(last.node.clone())
                        });
                    }
                }
            }
        }

        let default = default_model.as_ref();
        let req = AgentSidecarRunStartRequest {
            run_id: Some(run_id.clone()),
            user: user.clone(),
            system,
            kind: Some("price_compare".to_string()),
            node_models: Some(node_models),
            default_base_url: default.map(|d| d.base_url.clone()),
            default_api_key: default.map(|d| d.api_key.clone()),
            default_model: default.map(|d| d.model.clone()),
            resume_from_run_id,
            resume_state_json,
            resume_node: seek_node,
            trace_id: Some(run_id.clone()),
        };

        let resp = agent_run::start(&self.client, &req)
            .await
            .map_err(|e| e.to_string())?;
        if !resp.ok {
            return Err(resp.message.unwrap_or_else(|| "start_run 失败".to_string()));
        }

        info!(
            target: RUNTIME_TARGET,
            run_id = %resp.run_id,
            user = %user.chars().take(160).collect::<String>(),
            "[runtime] agent.run.start"
        );

        let record = AgentRunRecord {
            id: resp.run_id.clone(),
            kind: "price_compare".to_string(),
            state: resp.state.clone(),
            user,
            reply: None,
            error: None,
            error_kind: None,
            failed_node: None,
            steps: inherited_steps,
            created_at: now,
            updated_at: now,
            finished_at: None,
        };
        self.store_upsert(record.clone())?;
        *self.active_run_id.write().expect("active") = Some(resp.run_id.clone());
        self.lifecycle.transition(AgentState::Running);
        self.emit_progress(&AgentProgressEvent {
            run_id: resp.run_id.clone(),
            step_id: None,
            node: None,
            index: None,
            total: Some(8),
            status: "running".to_string(),
            message: "run started".to_string(),
            detail: None,
            error_kind: None,
            account_id: None,
            model: None,
            content: None,
        });
        Ok(record)
    }

    pub async fn pause_run(&self, run_id: Option<String>) -> Result<AgentRunRecord, String> {
        let id = self.resolve_run_id(run_id)?;
        info!(
            target: RUNTIME_TARGET,
            run_id = %id,
            action = "pause",
            "[runtime] agent.run.control.in"
        );
        let resp = agent_run::control(
            &self.client,
            &AgentSidecarRunControlRequest {
                run_id: id.clone(),
                action: "pause".to_string(),
                node: None,
                node_model: None,
                trace_id: Some(id.clone()),
            },
        )
        .await
        .map_err(|e| e.to_string())?;
        if !resp.ok {
            return Err(resp.message.unwrap_or_else(|| "pause 失败".to_string()));
        }
        info!(
            target: RUNTIME_TARGET,
            run_id = %id,
            state = %resp.state,
            "[runtime] agent.run.control.out"
        );
        self.lifecycle.transition(AgentState::Paused);
        self.patch_run_state(&id, "paused", None, None, None)
    }

    pub async fn resume_run(
        &self,
        run_id: Option<String>,
        mode: &str,
        node: Option<String>,
        node_model: Option<AgentSidecarNodeModel>,
    ) -> Result<AgentRunRecord, String> {
        let id = self.resolve_run_id(run_id)?;
        let action = match mode {
            "continue" | "restart" | "seek" => mode,
            other => return Err(format!("未知 resume mode: {other}")),
        };
        if action == "seek" && node.as_ref().map(|s| s.is_empty()).unwrap_or(true) {
            return Err("seek 需要 node".to_string());
        }
        info!(
            target: RUNTIME_TARGET,
            run_id = %id,
            action = %action,
            node = %node.as_deref().unwrap_or("-"),
            "[runtime] agent.run.control.in"
        );
        let resp = agent_run::control(
            &self.client,
            &AgentSidecarRunControlRequest {
                run_id: id.clone(),
                action: action.to_string(),
                node,
                node_model,
                trace_id: Some(id.clone()),
            },
        )
        .await
        .map_err(|e| e.to_string())?;
        if !resp.ok {
            return Err(resp.message.unwrap_or_else(|| "resume 失败".to_string()));
        }
        info!(
            target: RUNTIME_TARGET,
            run_id = %id,
            state = %resp.state,
            "[runtime] agent.run.control.out"
        );
        self.lifecycle.transition(AgentState::Running);
        self.patch_run_state(&id, "running", None, None, None)
    }

    pub async fn cancel_run(&self, run_id: Option<String>) -> Result<AgentRunRecord, String> {
        let id = self.resolve_run_id(run_id)?;
        self.cancel_network_wait();
        let resp = agent_run::cancel(
            &self.client,
            &AgentSidecarRunCancelRequest {
                run_id: id.clone(),
                trace_id: Some(id.clone()),
            },
        )
        .await
        .map_err(|e| e.to_string())?;
        if !resp.ok {
            return Err(resp.message.unwrap_or_else(|| "cancel 失败".to_string()));
        }
        self.lifecycle.transition(AgentState::Ready);
        self.patch_run_state(
            &id,
            "cancelled",
            None,
            None,
            Some(Utc::now().timestamp_millis()),
        )
    }

    pub async fn run_status(&self, run_id: Option<String>) -> Result<AgentRunRecord, String> {
        let id = self.resolve_run_id(run_id)?;
        if let Some(local) = self.store_get(&id) {
            return Ok(local);
        }
        Err(format!("run 不存在: {id}"))
    }

    pub fn list_runs(&self) -> Vec<AgentRunRecord> {
        self.store
            .read()
            .expect("store")
            .as_ref()
            .map(|s| s.list())
            .unwrap_or_default()
    }

    fn resolve_run_id(&self, run_id: Option<String>) -> Result<String, String> {
        if let Some(id) = run_id.filter(|s| !s.trim().is_empty()) {
            return Ok(id);
        }
        self.active_run_id
            .read()
            .expect("active")
            .clone()
            .ok_or_else(|| "没有活动 run".to_string())
    }

    async fn ai_config(&self) -> Result<AiIpcConfigResponse, String> {
        let cfg = self
            .config
            .read()
            .expect("config")
            .clone()
            .ok_or_else(|| "AgentRuntime 未 configure".to_string())?;
        cfg.ai_get().await.map_err(|e| e.to_string())
    }

    fn store_get(&self, id: &str) -> Option<AgentRunRecord> {
        self.store
            .read()
            .expect("store")
            .as_ref()
            .and_then(|s| s.get(id))
    }

    fn store_upsert(&self, run: AgentRunRecord) -> Result<(), String> {
        let store = self
            .store
            .read()
            .expect("store")
            .clone()
            .ok_or_else(|| "AgentRuntime 未 configure".to_string())?;
        store.upsert(run).map_err(|e| e.to_string())
    }

    fn patch_run_state(
        &self,
        id: &str,
        state: &str,
        error: Option<String>,
        error_kind: Option<String>,
        finished_at: Option<i64>,
    ) -> Result<AgentRunRecord, String> {
        let mut run = self
            .store_get(id)
            .ok_or_else(|| format!("run 不存在: {id}"))?;
        run.state = state.to_string();
        run.updated_at = Utc::now().timestamp_millis();
        if error.is_some() {
            run.error = error;
        }
        if error_kind.is_some() {
            run.error_kind = error_kind;
        }
        if finished_at.is_some() {
            run.finished_at = finished_at;
        }
        self.store_upsert(run.clone())?;
        Ok(run)
    }

    fn emit_progress(&self, event: &AgentProgressEvent) {
        if let Some(sink) = self.event_sink.read().expect("sink").as_ref() {
            let _ = emit(sink.as_ref(), &AppEvent::AgentProgress(event.clone()));
        }
    }

    fn cancel_network_wait(&self) {
        if let Some(tx) = self.network_wait_cancel.write().expect("net").take() {
            let _ = tx.send(true);
        }
    }
}

/// 带 Arc 的观察循环入口（由 cmd / supervisor 调用）。
pub async fn observe_run(runtime: Arc<AgentRuntime>, run_id: String) {
    let mut since_index = 0i64;
    loop {
        tokio::time::sleep(Duration::from_millis(400)).await;
        let status = match agent_run::status(
            &runtime.client,
            &AgentSidecarRunStatusRequest {
                run_id: run_id.clone(),
                since_index: Some(since_index),
                trace_id: Some(run_id.clone()),
            },
        )
        .await
        {
            Ok(s) => s,
            Err(error) => {
                warn!(target: RUNTIME_TARGET, %error, "[runtime] agent.run.status.failed");
                continue;
            }
        };
        if !status.ok {
            continue;
        }

        if let Some(steps) = status.steps.as_ref() {
            for step in steps {
                let step_id = Uuid::new_v4().to_string();
                let rec = AgentStepRecord {
                    id: step_id.clone(),
                    node: step.node.clone(),
                    index: step.index,
                    status: step.status.clone(),
                    label: step.label.clone(),
                    detail: step.detail.clone(),
                    error_kind: step.error_kind.clone(),
                    account_id: step.account_id.clone(),
                    model: step.model.clone(),
                    content: step.content.clone(),
                    state_before_json: step.state_before_json.clone(),
                };
                if let Some(mut run) = runtime.store_get(&run_id) {
                    // upsert step by index
                    if let Some(existing) = run.steps.iter_mut().find(|s| s.index == rec.index) {
                        *existing = rec.clone();
                    } else {
                        run.steps.push(rec.clone());
                    }
                    run.state = status.state.clone();
                    run.updated_at = Utc::now().timestamp_millis();
                    run.reply = status.reply.clone();
                    run.error = status.error.clone();
                    run.error_kind = status.error_kind.clone();
                    run.failed_node = status.failed_node.clone();
                    let _ = runtime.store_upsert(run);
                }
                let content_preview = rec
                    .content
                    .as_deref()
                    .unwrap_or("")
                    .chars()
                    .take(160)
                    .collect::<String>()
                    .replace('\n', " ");
                info!(
                    target: RUNTIME_TARGET,
                    run_id = %run_id,
                    index = rec.index,
                    node = %rec.node,
                    status = %rec.status,
                    model = %rec.model.as_deref().unwrap_or("-"),
                    content_chars = rec.content.as_ref().map(|c| c.len()).unwrap_or(0),
                    preview = %content_preview,
                    "[runtime] agent.run.step"
                );
                runtime.emit_progress(&AgentProgressEvent {
                    run_id: run_id.clone(),
                    step_id: Some(step_id),
                    node: Some(step.node.clone()),
                    index: Some(step.index),
                    total: Some(8),
                    status: step.status.clone(),
                    message: step.label.clone().unwrap_or_else(|| step.node.clone()),
                    detail: step.detail.clone(),
                    error_kind: step.error_kind.clone(),
                    account_id: step.account_id.clone(),
                    model: step.model.clone(),
                    content: step.content.clone(),
                });
                // 仅终态推进游标；running 时若推进会丢掉同 index 的 done/content。
                if step.status == "done" || step.status == "error" {
                    since_index = since_index.max(step.index + 1);
                }
            }
        }

        match status.state.as_str() {
            "completed" => {
                runtime.lifecycle.transition(AgentState::Ready);
                if let Some(mut run) = runtime.store_get(&run_id) {
                    run.state = "completed".to_string();
                    run.reply = status.reply.clone();
                    run.error = None;
                    run.error_kind = None;
                    run.updated_at = Utc::now().timestamp_millis();
                    run.finished_at = Some(run.updated_at);
                    let _ = runtime.store_upsert(run);
                }
                runtime.emit_progress(&AgentProgressEvent {
                    run_id: run_id.clone(),
                    step_id: None,
                    node: None,
                    index: None,
                    total: Some(8),
                    status: "completed".to_string(),
                    message: "done".to_string(),
                    detail: status.reply.clone(),
                    error_kind: None,
                    account_id: None,
                    model: None,
                    content: status.reply.clone(),
                });
                break;
            }
            "cancelled" => {
                runtime.lifecycle.transition(AgentState::Ready);
                let _ = runtime.patch_run_state(
                    &run_id,
                    "cancelled",
                    None,
                    None,
                    Some(Utc::now().timestamp_millis()),
                );
                break;
            }
            "paused" => {
                runtime.lifecycle.transition(AgentState::Paused);
                let _ = runtime.patch_run_state(&run_id, "paused", None, None, None);
                // keep observing until resume / cancel / terminal
                continue;
            }
            "waiting_network" => {
                runtime.lifecycle.transition(AgentState::WaitingNetwork);
                let _ = runtime.patch_run_state(
                    &run_id,
                    "waiting_network",
                    status.error.clone(),
                    status.error_kind.clone(),
                    None,
                );
                runtime.emit_progress(&AgentProgressEvent {
                    run_id: run_id.clone(),
                    step_id: None,
                    node: status.failed_node.clone(),
                    index: None,
                    total: Some(8),
                    status: "waiting_network".to_string(),
                    message: "等待网络恢复".to_string(),
                    detail: status.error.clone(),
                    error_kind: Some("network".to_string()),
                    account_id: None,
                    model: None,
                    content: None,
                });
                let failed = status.failed_node.clone().unwrap_or_default();
                wait_network_then_seek(runtime.clone(), run_id.clone(), failed).await;
                since_index = 0;
                continue;
            }
            "failed" => {
                let kind = status.error_kind.clone().unwrap_or_default();
                if kind == "network" {
                    // treat as waiting_network
                    runtime.lifecycle.transition(AgentState::WaitingNetwork);
                    let _ = runtime.patch_run_state(
                        &run_id,
                        "waiting_network",
                        status.error.clone(),
                        status.error_kind.clone(),
                        None,
                    );
                    let failed = status.failed_node.clone().unwrap_or_default();
                    wait_network_then_seek(runtime.clone(), run_id.clone(), failed).await;
                    // after seek, continue observing
                    since_index = 0;
                    continue;
                }
                if kind == "billing" {
                    if try_billing_failover(runtime.clone(), &run_id, status.failed_node.as_deref())
                        .await
                    {
                        since_index = 0;
                        continue;
                    }
                }
                runtime.lifecycle.transition(AgentState::Failed);
                let _ = runtime.patch_run_state(
                    &run_id,
                    "failed",
                    status.error.clone(),
                    status.error_kind.clone(),
                    Some(Utc::now().timestamp_millis()),
                );
                runtime.emit_progress(&AgentProgressEvent {
                    run_id: run_id.clone(),
                    step_id: None,
                    node: status.failed_node.clone(),
                    index: None,
                    total: Some(8),
                    status: "failed".to_string(),
                    message: status.error.clone().unwrap_or_else(|| "failed".to_string()),
                    detail: None,
                    error_kind: status.error_kind.clone(),
                    account_id: None,
                    model: None,
                    content: None,
                });
                break;
            }
            _ => {}
        }
    }
}

async fn try_billing_failover(
    runtime: Arc<AgentRuntime>,
    run_id: &str,
    failed_node: Option<&str>,
) -> bool {
    let Some(node) = failed_node.map(str::to_string).filter(|s| !s.is_empty()) else {
        return false;
    };
    let Ok(config) = runtime.ai_config().await else {
        return false;
    };
    let next = {
        let mut cursor = runtime.failover_cursor.write().expect("failover");
        if cursor.is_empty() {
            return false;
        }
        cursor.remove(0)
    };
    let Ok(resolved) = resolve_account(&config, &next) else {
        return false;
    };
    info!(
        target: RUNTIME_TARGET,
        run_id = %run_id,
        node = %node,
        account = %next,
        "[runtime] agent.billing.failover"
    );
    let node_model = resolved.to_sidecar(&node);
    match runtime
        .resume_run(
            Some(run_id.to_string()),
            "seek",
            Some(node),
            Some(node_model),
        )
        .await
    {
        Ok(_) => true,
        Err(error) => {
            warn!(target: RUNTIME_TARGET, %error, "[runtime] agent.billing.failover.failed");
            false
        }
    }
}

async fn wait_network_then_seek(runtime: Arc<AgentRuntime>, run_id: String, failed_node: String) {
    let (tx, mut rx) = tokio::sync::watch::channel(false);
    *runtime.network_wait_cancel.write().expect("net") = Some(tx);
    let probe_host = runtime
        .ai_config()
        .await
        .ok()
        .and_then(|c| c.providers.first().and_then(|p| p.base_url.clone()))
        .unwrap_or_else(|| "https://www.baidu.com".to_string());

    loop {
        if *rx.borrow() {
            break;
        }
        if probe_online(&probe_host).await {
            runtime.cancel_network_wait();
            if !failed_node.is_empty() {
                let _ = runtime
                    .resume_run(Some(run_id.clone()), "seek", Some(failed_node), None)
                    .await;
            }
            break;
        }
        tokio::select! {
            _ = tokio::time::sleep(Duration::from_secs(3)) => {}
            _ = rx.changed() => {
                if *rx.borrow() { break; }
            }
        }
    }
}

async fn probe_online(base_url: &str) -> bool {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build();
    let Ok(client) = client else {
        return false;
    };
    let url = if base_url.starts_with("http") {
        base_url.to_string()
    } else {
        format!("https://{base_url}")
    };
    client.get(&url).send().await.is_ok()
}

impl AgentRuntime {
    /// Arc 友好：start_run 后自动观察。
    pub async fn start_run_tracked(
        self: &Arc<Self>,
        user: String,
        system: Option<String>,
        resume_from_run_id: Option<String>,
        resume_node: Option<String>,
    ) -> Result<AgentRunRecord, String> {
        let record = self
            .start_run(user, system, resume_from_run_id, resume_node)
            .await?;
        let runtime = Arc::clone(self);
        let run_id = record.id.clone();
        tauri::async_runtime::spawn(async move {
            observe_run(runtime, run_id).await;
        });
        Ok(record)
    }
}
