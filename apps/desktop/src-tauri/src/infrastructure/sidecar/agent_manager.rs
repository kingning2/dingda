//! Agent Runtime 管理 — 生命周期 + 可控 graph run（pause/seek/failover/网络探活）。

use std::sync::{Arc, RwLock};
use std::time::Duration;

use chrono::Utc;
use uuid::Uuid;

use crate::config::ConfigStore;
use crate::contracts::events::{emit, AgentProgressEvent, AppEvent, EventSink};
use crate::contracts::{
    AgentSidecarNodeModel, AgentSidecarRunCancelRequest, AgentSidecarRunControlRequest,
    AgentSidecarRunStartRequest, AgentSidecarRunStatusRequest, AgentSidecarRunStep,
    AiIpcConfigResponse,
};
use crate::infrastructure::database::stores::InMemoryAccountStore;
use crate::infrastructure::runtime::RUNTIME_TARGET;
use crate::infrastructure::sidecar::agent_task;
use crate::infrastructure::sidecar::client::SidecarClient;
use crate::infrastructure::sidecar::connection::RpcEvent;

use serde::Deserialize;
use tokio::sync::broadcast::error::RecvError;

use super::agent_models::{build_node_models, failover_account_ids, resolve_account};
use super::agent_state::AgentLifecycle;
use super::agent_state::AgentState;
use super::agent_store::{AgentRunRecord, AgentRunStore, AgentStepRecord};
use super::agent_task::{resolve_crawl_channel, DEFAULT_OWNER_ID};

/// Agent Runtime 管理器。
pub struct AgentRuntime {
    lifecycle: AgentLifecycle,
    client: SidecarClient,
    event_sink: RwLock<Option<Arc<dyn EventSink>>>,
    config: RwLock<Option<Arc<ConfigStore>>>,
    store: RwLock<Option<Arc<AgentRunStore>>>,
    account_store: RwLock<Option<Arc<InMemoryAccountStore>>>,
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
            account_store: RwLock::new(None),
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
        account_store: Arc<InMemoryAccountStore>,
    ) {
        *self.event_sink.write().expect("agent sink") = Some(event_sink);
        *self.config.write().expect("agent config") = Some(config);
        *self.account_store.write().expect("agent accounts") = Some(account_store);
        // 冷启动：孤儿 run → interrupted
        if let Ok(ids) = store.mark_orphans_interrupted() {
            for id in ids {
                info!(target: RUNTIME_TARGET, run_id = %id, "[runtime] agent.run.interrupted");
            }
        }
        *self.store.write().expect("agent store") = Some(store);
    }

    /// 全局订阅 pipe `agent.run`（含副驾直连 Python 启动的 run）。
    pub fn spawn_pipe_listener(self: &Arc<Self>) {
        let runtime = Arc::clone(self);
        tauri::async_runtime::spawn(async move {
            spawn_agent_run_pipe_listener(runtime).await;
        });
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
        let crawl_channel = self
            .account_store
            .read()
            .expect("agent accounts")
            .as_ref()
            .and_then(|store| resolve_crawl_channel(store.as_ref(), DEFAULT_OWNER_ID));
        let (channel_account_id, cookies) = match crawl_channel {
            Some((id, cookies)) => {
                info!(
                    target: RUNTIME_TARGET,
                    account_id = %id,
                    cookies = cookies.len(),
                    "[runtime] agent.run.crawl_channel"
                );
                (Some(id), Some(cookies))
            }
            None => {
                warn!(
                    target: RUNTIME_TARGET,
                    "[runtime] agent.run.crawl_channel.missing"
                );
                (None, None)
            }
        };
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
            channel_account_id,
            cookies,
        };

        let resp = agent_task::run_start(&self.client, &req)
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
        let resp = agent_task::run_control(
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
        let resp = agent_task::run_control(
            &self.client,
            &AgentSidecarRunControlRequest {
                run_id: id.clone(),
                action: action.to_string(),
                node: node.clone(),
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
        let mut run = self.patch_run_state(&id, "running", None, None, None)?;
        run.finished_at = None;
        if action == "restart" {
            run.steps.clear();
            run.reply = None;
            run.error = None;
            run.error_kind = None;
            run.failed_node = None;
        } else if action == "seek" {
            if let Some(target) = node.as_ref() {
                if let Some(index) = run
                    .steps
                    .iter()
                    .find(|s| s.node == *target)
                    .map(|s| s.index)
                {
                    run.steps.retain(|s| s.index < index);
                } else {
                    run.steps.clear();
                }
            }
            run.reply = None;
            run.error = None;
            run.error_kind = None;
            run.failed_node = None;
        }
        self.store_upsert(run.clone())?;
        Ok(run)
    }

    pub async fn cancel_run(&self, run_id: Option<String>) -> Result<AgentRunRecord, String> {
        let id = self.resolve_run_id(run_id)?;
        self.cancel_network_wait();
        let resp = agent_task::run_cancel(
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

const AGENT_RUN_EVENT: &str = "agent.run";

#[derive(Debug, Deserialize)]
struct AgentRunPush {
    run_id: String,
    state: String,
    #[serde(default)]
    kind: Option<String>,
    #[serde(default)]
    user: Option<String>,
    #[serde(default)]
    reply: Option<String>,
    #[serde(default)]
    error: Option<String>,
    #[serde(default)]
    error_kind: Option<String>,
    #[serde(default)]
    failed_node: Option<String>,
    #[serde(default)]
    step: Option<AgentSidecarRunStep>,
}

fn new_record_from_push(push: &AgentRunPush) -> AgentRunRecord {
    let now = Utc::now().timestamp_millis();
    AgentRunRecord {
        id: push.run_id.clone(),
        kind: push
            .kind
            .clone()
            .unwrap_or_else(|| "price_compare".to_string()),
        state: push.state.clone(),
        user: push.user.clone().unwrap_or_default(),
        reply: push.reply.clone(),
        error: push.error.clone(),
        error_kind: push.error_kind.clone(),
        failed_node: push.failed_node.clone(),
        steps: vec![],
        created_at: now,
        updated_at: now,
        finished_at: None,
    }
}

fn merge_push_into_run(run: &mut AgentRunRecord, push: &AgentRunPush) {
    run.state = push.state.clone();
    run.updated_at = Utc::now().timestamp_millis();
    if push.reply.is_some() {
        run.reply = push.reply.clone();
    }
    if push.error.is_some() {
        run.error = push.error.clone();
    }
    if push.error_kind.is_some() {
        run.error_kind = push.error_kind.clone();
    }
    if push.failed_node.is_some() {
        run.failed_node = push.failed_node.clone();
    }
    if run.user.is_empty() {
        if let Some(user) = push.user.as_ref().filter(|value| !value.is_empty()) {
            run.user = user.clone();
        }
    }
    if run.kind.is_empty() {
        if let Some(kind) = push.kind.as_ref().filter(|value| !value.is_empty()) {
            run.kind = kind.clone();
        }
    }
}

/// 全局 pipe 监听：副驾等不经 `start_run` 的路径也能落库。
async fn spawn_agent_run_pipe_listener(runtime: Arc<AgentRuntime>) {
    loop {
        let mut rx = match runtime.client.subscribe_events().await {
            Ok(rx) => rx,
            Err(error) => {
                warn!(
                    target: RUNTIME_TARGET,
                    %error,
                    "[runtime] agent.run.global.subscribe.failed"
                );
                tokio::time::sleep(Duration::from_secs(1)).await;
                continue;
            }
        };
        info!(target: RUNTIME_TARGET, "[runtime] agent.run.global.subscribe");
        loop {
            match rx.recv().await {
                Ok(event) => {
                    if event.method != AGENT_RUN_EVENT {
                        continue;
                    }
                    let Ok(push) = serde_json::from_value::<AgentRunPush>(event.params) else {
                        continue;
                    };
                    apply_run_push(&runtime, &push).await;
                }
                Err(RecvError::Lagged(_)) => {
                    warn!(target: RUNTIME_TARGET, "[runtime] agent.run.global.lagged");
                }
                Err(RecvError::Closed) => {
                    warn!(target: RUNTIME_TARGET, "[runtime] agent.run.global.closed");
                    break;
                }
            }
        }
    }
}

fn run_is_terminal(runtime: &AgentRuntime, run_id: &str) -> bool {
    runtime
        .store_get(run_id)
        .map(|run| {
            matches!(
                run.state.as_str(),
                "completed" | "cancelled" | "failed" | "interrupted"
            )
        })
        .unwrap_or(true)
}

/// 订阅管道 `agent.run` Event；不再轮询 `/v1/agent/run/status`。
pub async fn observe_run(runtime: Arc<AgentRuntime>, run_id: String) {
    loop {
        if run_is_terminal(&runtime, &run_id) {
            return;
        }
        let mut rx = match runtime.client.subscribe_events().await {
            Ok(rx) => rx,
            Err(error) => {
                warn!(
                    target: RUNTIME_TARGET,
                    %error,
                    run_id = %run_id,
                    "[runtime] agent.run.subscribe.failed"
                );
                tokio::time::sleep(Duration::from_millis(200)).await;
                continue;
            }
        };
        info!(
            target: RUNTIME_TARGET,
            run_id = %run_id,
            "[runtime] agent.run.subscribe"
        );
        if catch_up_from_status(&runtime, &run_id).await {
            return;
        }
        loop {
            match rx.recv().await {
                Ok(event) => {
                    if apply_pipe_event(&runtime, &run_id, event).await {
                        return;
                    }
                }
                Err(RecvError::Lagged(skipped)) => {
                    warn!(
                        target: RUNTIME_TARGET,
                        skipped,
                        run_id = %run_id,
                        "[runtime] agent.run.subscribe.lagged"
                    );
                }
                Err(RecvError::Closed) => {
                    warn!(
                        target: RUNTIME_TARGET,
                        run_id = %run_id,
                        "[runtime] agent.run.subscribe.closed"
                    );
                    break;
                }
            }
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}

async fn catch_up_from_status(runtime: &Arc<AgentRuntime>, run_id: &str) -> bool {
    let status = match agent_task::run_status(
        &runtime.client,
        &AgentSidecarRunStatusRequest {
            run_id: run_id.to_string(),
            since_index: Some(0),
            trace_id: Some(run_id.to_string()),
        },
    )
    .await
    {
        Ok(s) if s.ok => s,
        _ => return false,
    };
    let push = AgentRunPush {
        run_id: status.run_id,
        state: status.state,
        kind: None,
        user: None,
        reply: status.reply,
        error: status.error,
        error_kind: status.error_kind,
        failed_node: status.failed_node,
        step: None,
    };
    if let Some(steps) = status.steps {
        for step in steps {
            apply_step(runtime, run_id, &push, &step);
        }
    }
    apply_run_push(runtime, &push).await
}

async fn apply_pipe_event(runtime: &Arc<AgentRuntime>, run_id: &str, event: RpcEvent) -> bool {
    if event.method != AGENT_RUN_EVENT {
        return false;
    }
    let Ok(push) = serde_json::from_value::<AgentRunPush>(event.params) else {
        return false;
    };
    if push.run_id != run_id {
        return false;
    }
    apply_run_push(runtime, &push).await
}

async fn apply_run_push(runtime: &Arc<AgentRuntime>, push: &AgentRunPush) -> bool {
    let run_id = &push.run_id;
    if push.step.is_none() && runtime.store_get(run_id).is_none() {
        let record = new_record_from_push(push);
        let _ = runtime.store_upsert(record.clone());
        *runtime.active_run_id.write().expect("active") = Some(run_id.clone());
        runtime.lifecycle.transition(AgentState::Running);
        runtime.emit_progress(&AgentProgressEvent {
            run_id: run_id.clone(),
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
    }
    if let Some(step) = push.step.as_ref() {
        apply_step(runtime, run_id, push, step);
    }

    match push.state.as_str() {
        "completed" => {
            runtime.lifecycle.transition(AgentState::Ready);
            if let Some(mut run) = runtime.store_get(run_id) {
                run.state = "completed".to_string();
                run.reply = push.reply.clone();
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
                detail: push.reply.clone(),
                error_kind: None,
                account_id: None,
                model: None,
                content: push.reply.clone(),
            });
            true
        }
        "cancelled" => {
            runtime.lifecycle.transition(AgentState::Ready);
            let _ = runtime.patch_run_state(
                run_id,
                "cancelled",
                None,
                None,
                Some(Utc::now().timestamp_millis()),
            );
            true
        }
        "paused" => {
            runtime.lifecycle.transition(AgentState::Paused);
            let _ = runtime.patch_run_state(run_id, "paused", None, None, None);
            false
        }
        "waiting_network" => {
            runtime.lifecycle.transition(AgentState::WaitingNetwork);
            let _ = runtime.patch_run_state(
                run_id,
                "waiting_network",
                push.error.clone(),
                push.error_kind.clone(),
                None,
            );
            runtime.emit_progress(&AgentProgressEvent {
                run_id: run_id.clone(),
                step_id: None,
                node: push.failed_node.clone(),
                index: None,
                total: Some(8),
                status: "waiting_network".to_string(),
                message: "等待网络恢复".to_string(),
                detail: push.error.clone(),
                error_kind: Some("network".to_string()),
                account_id: None,
                model: None,
                content: None,
            });
            let failed = push.failed_node.clone().unwrap_or_default();
            wait_network_then_seek(runtime.clone(), run_id.clone(), failed).await;
            false
        }
        "failed" => {
            let kind = push.error_kind.clone().unwrap_or_default();
            if kind == "network" {
                runtime.lifecycle.transition(AgentState::WaitingNetwork);
                let _ = runtime.patch_run_state(
                    run_id,
                    "waiting_network",
                    push.error.clone(),
                    push.error_kind.clone(),
                    None,
                );
                let failed = push.failed_node.clone().unwrap_or_default();
                wait_network_then_seek(runtime.clone(), run_id.clone(), failed).await;
                return false;
            }
            if kind == "billing"
                && try_billing_failover(runtime.clone(), run_id, push.failed_node.as_deref()).await
            {
                return false;
            }
            runtime.lifecycle.transition(AgentState::Failed);
            let _ = runtime.patch_run_state(
                run_id,
                "failed",
                push.error.clone(),
                push.error_kind.clone(),
                Some(Utc::now().timestamp_millis()),
            );
            runtime.emit_progress(&AgentProgressEvent {
                run_id: run_id.clone(),
                step_id: None,
                node: push.failed_node.clone(),
                index: None,
                total: Some(8),
                status: "failed".to_string(),
                message: push.error.clone().unwrap_or_else(|| "failed".to_string()),
                detail: None,
                error_kind: push.error_kind.clone(),
                account_id: None,
                model: None,
                content: None,
            });
            true
        }
        _ => false,
    }
}

fn apply_step(
    runtime: &AgentRuntime,
    run_id: &str,
    push: &AgentRunPush,
    step: &AgentSidecarRunStep,
) {
    let mut rec = AgentStepRecord {
        id: Uuid::new_v4().to_string(),
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
    let mut status_changed = true;
    let mut run = runtime
        .store_get(run_id)
        .unwrap_or_else(|| new_record_from_push(push));
    if let Some(existing) = run.steps.iter().find(|s| s.index == rec.index) {
        rec.id = existing.id.clone();
        if existing.status == rec.status && existing.content == rec.content {
            return;
        }
        status_changed = existing.status != rec.status;
    }
    if let Some(existing) = run.steps.iter_mut().find(|s| s.index == rec.index) {
        *existing = rec.clone();
    } else {
        run.steps.push(rec.clone());
    }
    merge_push_into_run(&mut run, push);
    let _ = runtime.store_upsert(run);
    if status_changed {
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
    }
    runtime.emit_progress(&AgentProgressEvent {
        run_id: run_id.to_string(),
        step_id: Some(rec.id.clone()),
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

    /// resume / seek / restart 后：若先前已终态，重新订阅管道。
    pub async fn resume_run_tracked(
        self: &Arc<Self>,
        run_id: Option<String>,
        mode: &str,
        node: Option<String>,
        node_model: Option<AgentSidecarNodeModel>,
    ) -> Result<AgentRunRecord, String> {
        let id = self.resolve_run_id(run_id.clone())?;
        let was_terminal = run_is_terminal(self, &id);
        let record = self
            .resume_run(Some(id.clone()), mode, node, node_model)
            .await?;
        if was_terminal {
            let runtime = Arc::clone(self);
            tauri::async_runtime::spawn(async move {
                observe_run(runtime, id).await;
            });
        }
        Ok(record)
    }
}

/// Agent Runtime 作为受管组件接入 [`crate::core::RuntimeSupervisor`]。
#[async_trait::async_trait]
impl crate::core::lifecycle::Component for AgentRuntime {
    fn id(&self) -> &'static str {
        "agent-runtime"
    }

    fn state(&self) -> crate::core::lifecycle::ComponentState {
        match self.state() {
            AgentState::Stopped => crate::contracts::RuntimeComponentState::Stopped,
            AgentState::Starting => crate::contracts::RuntimeComponentState::Starting,
            AgentState::Ready | AgentState::Running => {
                crate::contracts::RuntimeComponentState::Running
            }
            AgentState::Paused | AgentState::WaitingNetwork => {
                crate::contracts::RuntimeComponentState::Degraded
            }
            AgentState::Stopping => crate::contracts::RuntimeComponentState::Stopping,
            AgentState::Failed => crate::contracts::RuntimeComponentState::Failed,
        }
    }

    async fn start(&self) -> Result<(), String> {
        self.start().await
    }

    async fn stop(&self) -> Result<(), String> {
        AgentRuntime::stop(self);
        Ok(())
    }

    async fn health(&self) -> crate::core::lifecycle::HealthReport {
        crate::core::lifecycle::HealthReport::ok()
    }
}
