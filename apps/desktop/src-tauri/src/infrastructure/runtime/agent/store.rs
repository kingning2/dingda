//! Agent run 持久化 — JSON 文件（config_dir/agent-runs.json）。

use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::RwLock;

use crate::contracts::DingDaResult;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentRunRecord {
    pub id: String,
    pub kind: String,
    pub state: String,
    pub user: String,
    #[serde(default)]
    pub reply: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub error_kind: Option<String>,
    #[serde(default)]
    pub failed_node: Option<String>,
    #[serde(default)]
    pub steps: Vec<AgentStepRecord>,
    pub created_at: i64,
    pub updated_at: i64,
    #[serde(default)]
    pub finished_at: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentStepRecord {
    pub id: String,
    pub node: String,
    pub index: i64,
    pub status: String,
    #[serde(default)]
    pub label: Option<String>,
    #[serde(default)]
    pub detail: Option<String>,
    #[serde(default)]
    pub error_kind: Option<String>,
    #[serde(default)]
    pub account_id: Option<String>,
    #[serde(default)]
    pub model: Option<String>,
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub state_before_json: Option<String>,
}

#[derive(Default)]
struct StoreInner {
    runs: HashMap<String, AgentRunRecord>,
}

pub struct AgentRunStore {
    path: PathBuf,
    inner: RwLock<StoreInner>,
}

impl AgentRunStore {
    pub fn new(config_dir: PathBuf) -> Self {
        let path = config_dir.join("agent-runs.json");
        let mut inner = StoreInner::default();
        if let Ok(bytes) = std::fs::read(&path) {
            if let Ok(map) = serde_json::from_slice::<HashMap<String, AgentRunRecord>>(&bytes) {
                inner.runs = map;
            }
        }
        Self {
            path,
            inner: RwLock::new(inner),
        }
    }

    fn persist(&self, guard: &StoreInner) -> DingDaResult<()> {
        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| crate::contracts::DingDaError::store(e.to_string()))?;
        }
        let bytes = serde_json::to_vec_pretty(&guard.runs)
            .map_err(|e| crate::contracts::DingDaError::store(e.to_string()))?;
        std::fs::write(&self.path, bytes)
            .map_err(|e| crate::contracts::DingDaError::store(e.to_string()))?;
        Ok(())
    }

    pub fn upsert(&self, run: AgentRunRecord) -> DingDaResult<()> {
        let mut guard = self.inner.write().expect("agent run store");
        guard.runs.insert(run.id.clone(), run);
        self.persist(&guard)
    }

    pub fn get(&self, run_id: &str) -> Option<AgentRunRecord> {
        self.inner
            .read()
            .expect("agent run store")
            .runs
            .get(run_id)
            .cloned()
    }

    pub fn list(&self) -> Vec<AgentRunRecord> {
        let mut rows: Vec<_> = self
            .inner
            .read()
            .expect("agent run store")
            .runs
            .values()
            .cloned()
            .collect();
        rows.sort_by_key(|r| std::cmp::Reverse(r.created_at));
        rows
    }

    pub fn mark_orphans_interrupted(&self) -> DingDaResult<Vec<String>> {
        let mut guard = self.inner.write().expect("agent run store");
        let now = Utc::now().timestamp_millis();
        let mut ids = Vec::new();
        for run in guard.runs.values_mut() {
            if matches!(run.state.as_str(), "running" | "paused" | "waiting_network") {
                run.state = "interrupted".to_string();
                run.updated_at = now;
                run.finished_at = Some(now);
                ids.push(run.id.clone());
            }
        }
        if !ids.is_empty() {
            self.persist(&guard)?;
        }
        Ok(ids)
    }
}
