//! 闲鱼商品监控 — 任务与结果模型、SQLite Port、业务服务。
//!
//! 定时调度 / Sidecar 搜索 / AI 决策由 Tauri 壳层编排；本模块仅持久化与查询。

mod schedule;

pub use schedule::{
    bump_next_run_after_run, ensure_next_run_on_enable, is_schedule_due, pause_schedule,
    reset_and_pause_schedule_for_manual_run, resume_schedule, schedule_remaining_secs,
};

use chrono::Utc;
use common::events::MonitorProgressEvent;
use common::DingDaResult;
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// 监控任务。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MonitorTask {
    pub id: String,
    pub owner_id: i64,
    pub name: String,
    /// 用户意图描述，供 AI 生成搜索关键词。
    pub intent: String,
    /// AI 生成或人工校正后的关键词列表。
    pub keywords: Vec<String>,
    pub account_id: String,
    /// 全局 AI 配置中的账号 id；无账号平台用 `provider:{id}`（如 `provider:ollama`）。
    #[serde(default)]
    pub ai_account_id: String,
    /// 首选账号失败后是否自动切换备用 AI 账号。
    #[serde(default = "default_ai_failover_enabled")]
    pub ai_failover_enabled: bool,
    /// 备用 AI 账号顺序（不含首选）；为空则按 AI 配置自动推断。
    #[serde(default)]
    pub ai_account_order: Vec<String>,
    /// 定时间隔（分钟）。
    pub interval_minutes: u32,
    pub enabled: bool,
    /// 定时调度是否暂停（冻结剩余倒计时）。
    #[serde(default)]
    pub schedule_paused: bool,
    /// 暂停时冻结的剩余秒数。
    #[serde(default)]
    pub schedule_remaining_secs: Option<u64>,
    /// 下次定时运行时间（RFC3339）。
    #[serde(default)]
    pub next_run_at: Option<String>,
    /// AI 决策标准（自然语言）。
    pub ai_criteria: String,
    pub max_results: u32,
    /// 有头浏览器搜索（默认 true）。
    #[serde(default = "default_headed")]
    pub headed: bool,
    pub is_running: bool,
    pub last_run_at: Option<String>,
    pub last_error: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

fn default_headed() -> bool {
    true
}

fn default_ai_failover_enabled() -> bool {
    true
}

/// 监控命中结果。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MonitorResult {
    pub id: String,
    pub task_id: String,
    pub owner_id: i64,
    pub item_id: String,
    pub title: String,
    pub url: String,
    pub price_text: String,
    pub location: String,
    pub seller_name: String,
    pub ai_recommended: bool,
    pub ai_reason: String,
    pub notified: bool,
    #[serde(default)]
    pub raw: Value,
    /// 商品主图 URL（可能为空）。
    #[serde(default)]
    pub image: Option<String>,
    pub crawled_at: String,
}

/// 监控运行记录 — 每次任务执行一条，含状态、汇总与逐步步骤。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MonitorRun {
    pub id: String,
    pub task_id: String,
    pub owner_id: i64,
    /// `running` / `success` / `failed`。
    pub status: String,
    pub started_at: String,
    #[serde(default)]
    pub finished_at: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    pub scanned: u32,
    pub new_items: u32,
    pub skipped: u32,
    pub recommended: u32,
    /// 本次运行的逐步进度（与实时事件同构，供回看）。
    #[serde(default)]
    pub steps: Vec<MonitorProgressEvent>,
}

/// 监控整体统计（供概览条展示）。
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct MonitorStats {
    pub task_count: u32,
    pub running_count: u32,
    pub enabled_count: u32,
    pub result_count: u32,
    pub recommended_count: u32,
    pub today_new_count: u32,
}

/// 监控任务存储 Port。
pub trait MonitorTaskStore: Send + Sync {
    fn list_tasks(&self, owner_id: i64) -> DingDaResult<Vec<MonitorTask>>;
    fn get_task(&self, owner_id: i64, task_id: &str) -> DingDaResult<Option<MonitorTask>>;
    fn put_task(&self, task: &MonitorTask) -> DingDaResult<()>;
    fn delete_task(&self, owner_id: i64, task_id: &str) -> DingDaResult<()>;
}

/// 监控结果存储 Port。
pub trait MonitorResultStore: Send + Sync {
    fn list_results(&self, owner_id: i64, task_id: &str) -> DingDaResult<Vec<MonitorResult>>;
    fn list_all_results(&self, owner_id: i64) -> DingDaResult<Vec<MonitorResult>>;
    fn has_result(&self, owner_id: i64, task_id: &str, item_id: &str) -> DingDaResult<bool>;
    fn put_result(&self, result: &MonitorResult) -> DingDaResult<()>;
}

/// 监控运行记录存储 Port。
pub trait MonitorRunStore: Send + Sync {
    fn list_runs(&self, owner_id: i64, task_id: &str) -> DingDaResult<Vec<MonitorRun>>;
    fn get_run(&self, owner_id: i64, run_id: &str) -> DingDaResult<Option<MonitorRun>>;
    fn put_run(&self, run: &MonitorRun) -> DingDaResult<()>;
}

/// 监控业务服务。
pub struct MonitorService<'a> {
    tasks: &'a dyn MonitorTaskStore,
    results: &'a dyn MonitorResultStore,
    runs: &'a dyn MonitorRunStore,
}

impl<'a> MonitorService<'a> {
    pub fn new(
        tasks: &'a dyn MonitorTaskStore,
        results: &'a dyn MonitorResultStore,
        runs: &'a dyn MonitorRunStore,
    ) -> Self {
        Self {
            tasks,
            results,
            runs,
        }
    }

    pub fn list_tasks(&self, owner_id: i64) -> DingDaResult<Vec<MonitorTask>> {
        self.tasks.list_tasks(owner_id)
    }

    pub fn get_task(&self, owner_id: i64, task_id: &str) -> DingDaResult<Option<MonitorTask>> {
        self.tasks.get_task(owner_id, task_id)
    }

    pub fn save_task(&self, task: &MonitorTask) -> DingDaResult<()> {
        self.tasks.put_task(task)
    }

    pub fn delete_task(&self, owner_id: i64, task_id: &str) -> DingDaResult<()> {
        self.tasks.delete_task(owner_id, task_id)
    }

    pub fn list_results(&self, owner_id: i64, task_id: &str) -> DingDaResult<Vec<MonitorResult>> {
        let mut items = self.results.list_results(owner_id, task_id)?;
        items.sort_by(|a, b| b.crawled_at.cmp(&a.crawled_at));
        Ok(items)
    }

    pub fn has_seen(&self, owner_id: i64, task_id: &str, item_id: &str) -> DingDaResult<bool> {
        self.results.has_result(owner_id, task_id, item_id)
    }

    pub fn save_result(&self, result: &MonitorResult) -> DingDaResult<()> {
        self.results.put_result(result)
    }

    pub fn list_runs(&self, owner_id: i64, task_id: &str) -> DingDaResult<Vec<MonitorRun>> {
        let mut items = self.runs.list_runs(owner_id, task_id)?;
        items.sort_by(|a, b| b.started_at.cmp(&a.started_at));
        items.truncate(200);
        // 列表只回摘要，避免拉取大转录体量；详情页用 get_run 取完整 steps。
        for run in &mut items {
            run.steps.clear();
        }
        Ok(items)
    }

    pub fn get_run(&self, owner_id: i64, run_id: &str) -> DingDaResult<Option<MonitorRun>> {
        self.runs.get_run(owner_id, run_id)
    }

    pub fn save_run(&self, run: &MonitorRun) -> DingDaResult<()> {
        self.runs.put_run(run)
    }

    pub fn stats(&self, owner_id: i64) -> DingDaResult<MonitorStats> {
        let tasks = self.tasks.list_tasks(owner_id)?;
        let results = self.results.list_all_results(owner_id)?;
        let today = Utc::now().format("%Y-%m-%d").to_string();
        Ok(MonitorStats {
            task_count: tasks.len() as u32,
            running_count: tasks.iter().filter(|task| task.is_running).count() as u32,
            enabled_count: tasks.iter().filter(|task| task.enabled).count() as u32,
            result_count: results.len() as u32,
            recommended_count: results
                .iter()
                .filter(|result| result.ai_recommended)
                .count() as u32,
            today_new_count: results
                .iter()
                .filter(|result| result.crawled_at.starts_with(&today))
                .count() as u32,
        })
    }
}
