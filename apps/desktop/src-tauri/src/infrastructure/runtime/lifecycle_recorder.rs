//! 最小 Lifecycle Recorder — 旁路记录状态变化与已有 bus 事件。
//!
//! 不新建第二套 EventBus；不改变状态转换规则。
//! `DINGDA_E2E=true` 时可落盘 JSONL；生产默认仅内存 ring。

use std::fs::{create_dir_all, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;

use crate::infrastructure::event::{EventError, EventHandler};

const RING_CAPACITY: usize = 4096;

/// 单条生命周期记录（供 E2E / Timeline，非新生产事件协议）。
#[derive(Debug, Clone, Serialize)]
pub struct LifecycleRecord {
    pub timestamp: u128,
    pub component: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous_state: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<String>,
    pub source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pid: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub run_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub topic: Option<String>,
}

/// 是否处于 E2E 可观测模式（仅增强观测，不改业务路径）。
pub fn is_e2e_mode() -> bool {
    matches!(
        std::env::var("DINGDA_E2E").as_deref(),
        Ok("1") | Ok("true") | Ok("TRUE") | Ok("yes") | Ok("YES")
    )
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0)
}

struct RecorderInner {
    records: Vec<LifecycleRecord>,
    jsonl_path: Option<PathBuf>,
}

impl RecorderInner {
    fn new() -> Self {
        let jsonl_path = if is_e2e_mode() {
            let path = std::env::var("DINGDA_E2E_JSONL")
                .map(PathBuf::from)
                .unwrap_or_else(|_| PathBuf::from("tests/e2e/reports/runtime-events.jsonl"));
            if let Some(parent) = path.parent() {
                let _ = create_dir_all(parent);
            }
            // Truncate at start of process for a clean run.
            let _ = OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(true)
                .open(&path);
            Some(path)
        } else {
            None
        };
        Self {
            records: Vec::with_capacity(256),
            jsonl_path,
        }
    }

    fn append(&mut self, record: LifecycleRecord) {
        if let Some(path) = &self.jsonl_path {
            append_jsonl(path, &record);
        }
        if self.records.len() >= RING_CAPACITY {
            let drop_n = self.records.len() - RING_CAPACITY + 1;
            self.records.drain(0..drop_n);
        }
        self.records.push(record);
    }
}

fn append_jsonl(path: &Path, record: &LifecycleRecord) {
    let Ok(line) = serde_json::to_string(record) else {
        return;
    };
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) else {
        return;
    };
    let _ = writeln!(file, "{line}");
}

fn global() -> &'static Mutex<RecorderInner> {
    static RECORDER: OnceLock<Mutex<RecorderInner>> = OnceLock::new();
    RECORDER.get_or_init(|| Mutex::new(RecorderInner::new()))
}

/// 记录组件状态变化（幂等调用方应先判断 previous != new）。
pub fn record_state_change(
    component: &str,
    previous: &str,
    next: &str,
    pid: Option<u32>,
    task_id: Option<String>,
    run_id: Option<String>,
) {
    let record = LifecycleRecord {
        timestamp: now_ms(),
        component: component.to_string(),
        previous_state: Some(previous.to_string()),
        state: Some(next.to_string()),
        source: "state_change".to_string(),
        pid,
        error: None,
        run_id,
        task_id,
        topic: None,
    };
    if let Ok(mut guard) = global().lock() {
        guard.append(record);
    }
}

/// 记录已有 bus 事件摘要。
pub fn record_bus_event(topic: &str, error: Option<String>) {
    let (component, state) = match topic {
        "runtime/sidecar/restarted" => ("python", Some("restarted")),
        "runtime/error" => ("runtime", Some("error")),
        other if other.starts_with("app/agent/") => ("agent", Some("progress")),
        _ => ("bus", None),
    };
    let record = LifecycleRecord {
        timestamp: now_ms(),
        component: component.to_string(),
        previous_state: None,
        state: state.map(str::to_string),
        source: "bus".to_string(),
        pid: None,
        error,
        run_id: None,
        task_id: None,
        topic: Some(topic.to_string()),
    };
    if let Ok(mut guard) = global().lock() {
        guard.append(record);
    }
}

/// 快照当前缓冲（时间正序）。
pub fn snapshot() -> Vec<LifecycleRecord> {
    global()
        .lock()
        .map(|guard| guard.records.clone())
        .unwrap_or_default()
}

/// 清空缓冲（测试用）。
pub fn clear() {
    if let Ok(mut guard) = global().lock() {
        guard.records.clear();
    }
}

/// 将 EventBus 事件旁路写入 Recorder。
pub struct BusLifecycleHandler;

impl EventHandler for BusLifecycleHandler {
    fn handle(&self, topic: &str, payload: &[u8]) -> Result<(), EventError> {
        let error = serde_json::from_slice::<serde_json::Value>(payload)
            .ok()
            .and_then(|v| {
                v.get("message")
                    .and_then(|m| m.as_str())
                    .map(str::to_string)
            });
        record_bus_event(topic, error);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn records_state_changes_in_order() {
        clear();
        record_state_change("runtime", "starting", "initializing", None, None, None);
        record_state_change("python", "stopped", "starting", Some(42), None, None);
        record_state_change("python", "starting", "ready", Some(42), None, None);
        let events = snapshot();
        assert!(events.len() >= 3);
        let tail = &events[events.len() - 3..];
        assert_eq!(tail[0].component, "runtime");
        assert_eq!(tail[1].component, "python");
        assert_eq!(tail[1].pid, Some(42));
        assert_eq!(tail[2].state.as_deref(), Some("ready"));
    }
}
