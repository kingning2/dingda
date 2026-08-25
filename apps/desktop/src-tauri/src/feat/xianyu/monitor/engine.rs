//! 闲鱼监控任务执行引擎。

use crate::contracts::events::{
    emit, AppEvent, MonitorMatchEvent, MonitorProgressEvent, MonitorProgressStage,
    MonitorProgressSummary,
};
use crate::contracts::DingDaResult;
use crate::core::domain::monitor::{
    bump_next_run_after_run, MonitorResult, MonitorRun, MonitorRunStore, MonitorService,
    MonitorTask, MonitorTaskStore,
};
use crate::core::store::{
    InMemoryAccountStore, InMemoryMonitorResultStore, InMemoryMonitorRunStore,
    InMemoryMonitorTaskStore,
};
use chrono::Utc;
use serde_json::{json, Value};
use std::sync::Arc;
use uuid::Uuid;

use super::ai::{
    build_decision_prompt, build_keyword_prompt, decide_item, generate_keywords, AiFailoverContext,
};
use super::search::search_offers;
use crate::config::ConfigStore;
use crate::core::manager::python::SidecarLifecycle;
use crate::utils::state::AppState;

pub struct MonitorEngine {
    pub tasks: Arc<InMemoryMonitorTaskStore>,
    pub results: Arc<InMemoryMonitorResultStore>,
    pub runs: Arc<InMemoryMonitorRunStore>,
    pub app_state: Arc<AppState>,
    pub account_store: Arc<InMemoryAccountStore>,
    pub config_store: Arc<ConfigStore>,
    pub sidecar: Arc<SidecarLifecycle>,
    pub event_sink: Arc<dyn crate::contracts::events::EventSink>,
}

impl MonitorEngine {
    pub async fn run_task(&self, owner_id: i64, task_id: &str) -> DingDaResult<MonitorRunSummary> {
        let mut task = self
            .tasks
            .get_task(owner_id, task_id)?
            .ok_or_else(|| crate::contracts::DingDaError::validation("监控任务不存在"))?;
        if task.is_running {
            // 有正在运行的记录才算真的在跑；否则是上次中断残留标记，忽略后放行。
            let has_active_run = self
                .runs
                .list_runs(owner_id, &task.id)?
                .iter()
                .any(|run| run.status == "running");
            if has_active_run {
                return Err(crate::contracts::DingDaError::validation("任务正在运行中"));
            }
            task.is_running = false;
        }

        task.is_running = true;
        task.last_error = None;
        task.updated_at = Utc::now().to_rfc3339();
        self.tasks.put_task(&task)?;

        let run_id = Uuid::new_v4().to_string();
        let mut run = MonitorRun {
            id: run_id.clone(),
            task_id: task.id.clone(),
            owner_id,
            status: "running".to_string(),
            started_at: Utc::now().to_rfc3339(),
            finished_at: None,
            error: None,
            scanned: 0,
            new_items: 0,
            skipped: 0,
            recommended: 0,
            steps: Vec::new(),
        };
        self.runs.put_run(&run)?;
        self.emit_progress(
            &task,
            &run_id,
            MonitorProgressStage::Started,
            "任务开始运行".to_string(),
            None,
            None,
            &mut run.steps,
        );

        let result = self
            .run_task_inner(owner_id, &mut task, &run_id, &mut run.steps)
            .await;
        task.is_running = false;
        let finished_at = Utc::now();
        task.last_run_at = Some(finished_at.to_rfc3339());
        task.updated_at = finished_at.to_rfc3339();
        bump_next_run_after_run(&mut task, finished_at);
        match &result {
            Ok(summary) => {
                run.status = "success".to_string();
                run.scanned = summary.scanned;
                run.new_items = summary.new_items;
                run.skipped = summary.skipped;
                run.recommended = summary.recommended;
                run.finished_at = Some(Utc::now().to_rfc3339());
                let progress = MonitorProgressSummary {
                    scanned: summary.scanned,
                    new_items: summary.new_items,
                    skipped: summary.skipped,
                    recommended: summary.recommended,
                };
                self.emit_progress(
                    &task,
                    &run_id,
                    MonitorProgressStage::Finished,
                    format!(
                        "任务完成：扫描 {} 条，新增 {} 条，推荐 {} 条",
                        summary.scanned, summary.new_items, summary.recommended
                    ),
                    None,
                    Some(progress),
                    &mut run.steps,
                );
            }
            Err(error) => {
                run.status = "failed".to_string();
                run.error = Some(error.to_string());
                run.finished_at = Some(Utc::now().to_rfc3339());
                task.last_error = Some(error.to_string());
                self.emit_progress(
                    &task,
                    &run_id,
                    MonitorProgressStage::Failed,
                    "任务失败".to_string(),
                    Some(error.to_string()),
                    None,
                    &mut run.steps,
                );
            }
        }
        self.runs.put_run(&run)?;
        self.tasks.put_task(&task)?;
        result
    }

    /// 启动时清理上次中断残留：复位卡死的 `is_running`，并把 running 运行记录标为失败。
    pub fn recover_interrupted_runs(&self, owner_id: i64) -> DingDaResult<()> {
        let tasks = self.tasks.list_tasks(owner_id)?;
        for mut task in tasks {
            if task.is_running {
                task.is_running = false;
                task.last_error = Some("上次运行被中断，已自动重置".to_string());
                task.updated_at = Utc::now().to_rfc3339();
                self.tasks.put_task(&task)?;
            }
            let runs = self.runs.list_runs(owner_id, &task.id)?;
            for mut run in runs {
                if run.status == "running" {
                    run.status = "failed".to_string();
                    run.error = Some("运行被中断".to_string());
                    run.finished_at = Some(Utc::now().to_rfc3339());
                    self.runs.put_run(&run)?;
                }
            }
        }
        Ok(())
    }

    async fn run_task_inner(
        &self,
        owner_id: i64,
        task: &mut MonitorTask,
        run_id: &str,
        steps: &mut Vec<MonitorProgressEvent>,
    ) -> DingDaResult<MonitorRunSummary> {
        let ai_config = self
            .config_store
            .ai_get()
            .await
            .map_err(crate::contracts::DingDaError::wrap)?;
        let mut ai_failover = AiFailoverContext::new(
            &task.ai_account_id,
            task.ai_failover_enabled,
            task.ai_account_order.clone(),
        );

        if task.keywords.is_empty() {
            let prompt = build_keyword_prompt(&task.intent, &task.ai_criteria);
            self.emit_content(
                task,
                run_id,
                MonitorProgressStage::Keywords,
                "发送给 AI：生成搜索关键词".to_string(),
                "user",
                "text",
                truncate(&prompt, 1200),
                steps,
            );
            let generated =
                generate_keywords(self.sidecar.as_ref(), &ai_config, &mut ai_failover, &prompt)
                    .await
                    .map_err(crate::contracts::DingDaError::wrap)?;
            task.keywords = generated.keywords;
            task.updated_at = Utc::now().to_rfc3339();
            self.tasks.put_task(task)?;
            self.emit_content(
                task,
                run_id,
                MonitorProgressStage::Keywords,
                format!("AI 返回关键词（{} 个）", task.keywords.len()),
                "assistant",
                "json",
                truncate(&generated.raw, 2000),
                steps,
            );
        }
        self.emit_progress(
            task,
            run_id,
            MonitorProgressStage::Keywords,
            format!("关键词已就绪（{} 个）", task.keywords.len()),
            Some(task.keywords.join(" / ")),
            None,
            steps,
        );

        let service = MonitorService::new(
            self.tasks.as_ref(),
            self.results.as_ref(),
            self.runs.as_ref(),
        );
        let mut summary = MonitorRunSummary::default();

        for keyword in task.keywords.clone() {
            self.emit_progress(
                task,
                run_id,
                MonitorProgressStage::Search,
                format!("正在搜索「{keyword}」"),
                None,
                None,
                steps,
            );
            let outcome = search_offers(
                &self.app_state,
                self.account_store.as_ref(),
                owner_id,
                &task.account_id,
                &keyword,
                task.max_results as i64,
                false,
            )
            .await?;
            let scanned = outcome.offers.len() as u32;
            summary.scanned += scanned;
            self.emit_progress(
                task,
                run_id,
                MonitorProgressStage::Scanned,
                format!("「{keyword}」扫描到 {scanned} 条"),
                Some(outcome.detail.clone()),
                None,
                steps,
            );
            if outcome.status == "not_logged_in" || outcome.status == "error" {
                return Err(crate::contracts::DingDaError::validation(format!(
                    "「{keyword}」搜索失败：{}",
                    if outcome.detail.is_empty() {
                        "未知错误"
                    } else {
                        &outcome.detail
                    }
                )));
            }

            let scraped: Vec<Value> = outcome
                .offers
                .iter()
                .take(10)
                .map(|offer| {
                    json!({
                        "itemId": offer_item_id(offer).unwrap_or_default(),
                        "title": offer.get("title").and_then(Value::as_str).unwrap_or(""),
                        "price": offer.get("price")
                            .and_then(|value| value.get("text"))
                            .and_then(Value::as_str)
                            .unwrap_or(""),
                        "url": offer.get("url").and_then(Value::as_str).unwrap_or(""),
                    })
                })
                .collect();
            self.emit_content(
                task,
                run_id,
                MonitorProgressStage::Scanned,
                format!("爬虫返回 {scanned} 条（展示前 {} 条）", scraped.len()),
                "tool",
                "json",
                truncate(&serde_json::to_string(&scraped).unwrap_or_default(), 3000),
                steps,
            );

            let mut pending = 0u32;
            for offer in &outcome.offers {
                let Some(item_id) = offer_item_id(offer) else {
                    continue;
                };
                if service.has_seen(owner_id, &task.id, &item_id)? {
                    summary.skipped += 1;
                    continue;
                }
                pending += 1;
            }
            if pending == 0 {
                continue;
            }
            self.emit_progress(
                task,
                run_id,
                MonitorProgressStage::Decide,
                format!("AI 决策中：共 {pending} 件待判定"),
                None,
                None,
                steps,
            );

            for offer in outcome.offers {
                let Some(item_id) = offer_item_id(&offer) else {
                    continue;
                };
                if service.has_seen(owner_id, &task.id, &item_id)? {
                    continue;
                }

                let item_json = serde_json::to_string(&offer).unwrap_or_default();
                let prompt = build_decision_prompt(&task.ai_criteria, &item_json);
                self.emit_content(
                    task,
                    run_id,
                    MonitorProgressStage::Decide,
                    "发送给 AI 决策".to_string(),
                    "user",
                    "text",
                    truncate(&prompt, 1200),
                    steps,
                );
                let decided =
                    decide_item(self.sidecar.as_ref(), &ai_config, &mut ai_failover, &prompt)
                        .await
                        .map_err(crate::contracts::DingDaError::wrap)?;
                let decision = decided.decision;
                self.emit_content(
                    task,
                    run_id,
                    MonitorProgressStage::Decide,
                    "AI 返回决策".to_string(),
                    "assistant",
                    "json",
                    truncate(&decided.raw, 2000),
                    steps,
                );

                let result = build_result(owner_id, task, &item_id, &offer, &decision);
                service.save_result(&result)?;
                summary.new_items += 1;
                if decision.recommended {
                    summary.recommended += 1;
                    self.emit_progress(
                        task,
                        run_id,
                        MonitorProgressStage::Matched,
                        format!("推荐命中：{}", result.title),
                        Some(if result.price_text.is_empty() {
                            result.ai_reason.clone()
                        } else {
                            format!("{} | {}", result.price_text, result.ai_reason)
                        }),
                        None,
                        steps,
                    );
                    self.notify_match(task, &result)?;
                }
            }
        }

        Ok(summary)
    }

    /// 尽力而为的进度事件 — 同时写入运行记录步骤，不因事件下发失败中断爬取。
    #[allow(clippy::too_many_arguments)]
    fn emit_progress(
        &self,
        task: &MonitorTask,
        run_id: &str,
        stage: MonitorProgressStage,
        message: String,
        detail: Option<String>,
        summary: Option<MonitorProgressSummary>,
        steps: &mut Vec<MonitorProgressEvent>,
    ) {
        let payload = MonitorProgressEvent {
            step_id: Some(Uuid::new_v4().to_string()),
            run_id: run_id.to_string(),
            task_id: task.id.clone(),
            task_name: task.name.clone(),
            stage,
            message,
            detail,
            summary,
            content: None,
            content_kind: None,
            role: None,
        };
        steps.push(payload.clone());
        let _ = emit(
            self.event_sink.as_ref(),
            &AppEvent::MonitorProgress(payload),
        );
    }

    /// 内容步骤（发送给 AI / AI 返回 / 爬虫）— 同样写入运行记录步骤。
    #[allow(clippy::too_many_arguments)]
    fn emit_content(
        &self,
        task: &MonitorTask,
        run_id: &str,
        stage: MonitorProgressStage,
        message: String,
        role: &str,
        content_kind: &str,
        content: String,
        steps: &mut Vec<MonitorProgressEvent>,
    ) {
        let payload = MonitorProgressEvent {
            step_id: Some(Uuid::new_v4().to_string()),
            run_id: run_id.to_string(),
            task_id: task.id.clone(),
            task_name: task.name.clone(),
            stage,
            message,
            detail: None,
            summary: None,
            content: Some(content),
            content_kind: Some(content_kind.to_string()),
            role: Some(role.to_string()),
        };
        steps.push(payload.clone());
        let _ = emit(
            self.event_sink.as_ref(),
            &AppEvent::MonitorProgress(payload),
        );
    }

    fn notify_match(&self, task: &MonitorTask, result: &MonitorResult) -> DingDaResult<()> {
        let payload = MonitorMatchEvent {
            task_id: task.id.clone(),
            task_name: task.name.clone(),
            item_id: result.item_id.clone(),
            title: result.title.clone(),
            url: result.url.clone(),
            price_text: result.price_text.clone(),
            reason: result.ai_reason.clone(),
        };
        emit(self.event_sink.as_ref(), &AppEvent::MonitorMatch(payload))
    }
}

#[derive(Debug, Default, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MonitorRunSummary {
    pub scanned: u32,
    pub new_items: u32,
    pub skipped: u32,
    pub recommended: u32,
}

fn offer_item_id(offer: &Value) -> Option<String> {
    offer
        .get("itemId")
        .or_else(|| offer.get("item_id"))
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

/// 控制转录正文长度，超出加截断标记。
fn truncate(text: &str, max_chars: usize) -> String {
    if text.chars().count() <= max_chars {
        text.to_string()
    } else {
        let clipped: String = text.chars().take(max_chars).collect();
        format!("{clipped}…（已截断）")
    }
}

fn build_result(
    owner_id: i64,
    task: &MonitorTask,
    item_id: &str,
    offer: &Value,
    decision: &super::ai::MonitorAiDecision,
) -> MonitorResult {
    MonitorResult {
        id: Uuid::new_v4().to_string(),
        task_id: task.id.clone(),
        owner_id,
        item_id: item_id.to_string(),
        title: offer
            .get("title")
            .and_then(Value::as_str)
            .unwrap_or("未知标题")
            .to_string(),
        url: offer
            .get("url")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        price_text: offer
            .get("price")
            .and_then(|value| value.get("text"))
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        location: offer
            .get("location")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        seller_name: offer
            .get("seller")
            .and_then(|value| value.get("name"))
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        ai_recommended: decision.recommended,
        ai_reason: decision.reason.clone(),
        notified: decision.recommended,
        raw: offer.clone(),
        image: offer
            .get("image")
            .and_then(Value::as_str)
            .map(str::to_string),
        crawled_at: Utc::now().to_rfc3339(),
    }
}
