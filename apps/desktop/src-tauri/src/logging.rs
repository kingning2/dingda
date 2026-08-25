//! 应用日志初始化：终端输出 + 内存环形缓冲（供前端日志面板读取）。
//!
//! 终端统一格式：`【信息】14:32:05 python 侧车已启动 port=8879`
//! Python 侧车日志经 `log_pipe` 转发为 target `dingda.sidecar` 的 tracing 事件，
//! 因此本采集层可统一处理 Rust 与 Python 两侧日志，并在终端与 UI 中标注来源。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-13

use std::collections::VecDeque;
use std::io::{IsTerminal, Write};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;
use tracing::field::{Field, Visit};
use tracing::{Event, Level, Subscriber};
use tracing_subscriber::layer::{Context, SubscriberExt};
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::{EnvFilter, Layer, Registry};

/// 供前端日志面板展示的单条日志。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
#[derive(Debug, Clone, Serialize)]
pub struct LogEntry {
    /// Unix 毫秒时间戳。
    pub ts: u64,
    /// 级别：TRACE / DEBUG / INFO / WARN / ERROR。
    pub level: String,
    /// 来源：rust | python（Python 日志经 log_pipe 转发后标记为 python）。
    pub source: String,
    /// 目标模块（如 `dingda_lib::shared::channel::coordinator`）。
    pub target: String,
    /// 格式化后的日志消息。
    pub message: String,
}

/// 环形缓冲容量上限（超出后丢弃最旧的）。
const MAX_ENTRIES: usize = 2000;

/// 进程内日志环形缓冲。
struct LogBuffer {
    entries: Mutex<VecDeque<LogEntry>>,
}

impl LogBuffer {
    fn new() -> Self {
        Self {
            entries: Mutex::new(VecDeque::with_capacity(MAX_ENTRIES)),
        }
    }

    fn push(&self, entry: LogEntry) {
        let mut entries = self.entries.lock().expect("log buffer lock");
        if entries.len() >= MAX_ENTRIES {
            entries.pop_front();
        }
        entries.push_back(entry);
    }

    /// 取最近 `limit` 条，保持时间正序（旧 → 新）。
    fn recent(&self, limit: usize) -> Vec<LogEntry> {
        let entries = self.entries.lock().expect("log buffer lock");
        entries.iter().rev().take(limit).rev().cloned().collect()
    }

    fn clear(&self) {
        self.entries.lock().expect("log buffer lock").clear();
    }
}

static LOG_BUFFER: OnceLock<Arc<LogBuffer>> = OnceLock::new();

fn buffer() -> &'static Arc<LogBuffer> {
    LOG_BUFFER.get_or_init(|| Arc::new(LogBuffer::new()))
}

/// 读取最近日志（`log_recent` 命令使用）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
///
/// # 参数
/// - `limit` — 最多返回条数
///
/// # 返回值
/// 时间正序日志列表（旧 → 新）。
pub fn recent_logs(limit: usize) -> Vec<LogEntry> {
    buffer().recent(limit)
}

/// 清空日志缓冲（`log_clear` 命令使用）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
pub fn clear_logs() {
    buffer().clear();
}

/// 终端层：把每个事件按统一格式打到 stdout（等级带 ANSI 颜色）。
struct TerminalLayer {
    lock: Mutex<()>,
}

impl<S: Subscriber> Layer<S> for TerminalLayer {
    fn on_event(&self, event: &Event<'_>, _ctx: Context<'_, S>) {
        let (level, source, message) = event_info(event);
        let mut line = String::new();
        if std::io::stdout().is_terminal() {
            line.push_str(level_ansi(&level));
            line.push_str(&level);
            line.push_str("\x1b[0m");
        } else {
            line.push_str(&level);
        }
        line.push(' ');
        line.push_str(&beijing_time());
        line.push(' ');
        line.push_str(&source);
        line.push(' ');
        line.push_str(&message);
        line.push('\n');

        let _guard = self.lock.lock().expect("terminal lock");
        let mut stdout = std::io::stdout().lock();
        let _ = stdout.write_all(line.as_bytes());
        let _ = stdout.flush();
    }
}

/// 采集层：把事件写入环形缓冲，供日志面板读取。
struct LogCaptureLayer {
    buffer: Arc<LogBuffer>,
}

impl<S: Subscriber> Layer<S> for LogCaptureLayer {
    fn on_event(&self, event: &Event<'_>, _ctx: Context<'_, S>) {
        let (level, source, message) = event_info(event);
        let entry = LogEntry {
            ts: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_millis() as u64)
                .unwrap_or(0),
            level,
            source,
            target: event.metadata().target().to_string(),
            message,
        };
        self.buffer.push(entry);
    }
}

/// 从事件提取 (级别, 来源, 描述+参数) 三段，供终端与面板共用。
fn event_info(event: &Event<'_>) -> (String, String, String) {
    let mut visitor = MessageVisitor::default();
    event.record(&mut visitor);

    let mut message = visitor.message.unwrap_or_else(|| "(无消息)".to_string());
    if !visitor.fields.is_empty() {
        message.push(' ');
        message.push_str(&visitor.fields.join(" "));
    }

    let metadata = event.metadata();
    // Python 侧车日志统一以 `dingda.sidecar` target 转发进来。
    let source = if metadata.target() == "dingda.sidecar" {
        "python"
    } else {
        "rust"
    }
    .to_string();
    (level_str(metadata.level()), source, message)
}

fn level_str(level: &Level) -> String {
    match *level {
        Level::TRACE => "TRACE",
        Level::DEBUG => "DEBUG",
        Level::INFO => "INFO",
        Level::WARN => "WARN",
        Level::ERROR => "ERROR",
    }
    .to_string()
}

/// 等级 ANSI 颜色：错误红、警告黄、信息绿、调试灰。
fn level_ansi(level: &str) -> &'static str {
    match level {
        "ERROR" | "CRITICAL" => "\x1b[31m",
        "WARN" | "WARNING" => "\x1b[33m",
        "DEBUG" | "TRACE" => "\x1b[90m",
        _ => "\x1b[32m",
    }
}

/// 北京时间（UTC+8）YYYY-MM-DD HH:MM:SS。
fn beijing_time() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs() + 8 * 3600; // UTC+8
    let days = (secs / 86400) as i64;
    let rem = secs % 86400;
    let (h, m, s) = (rem / 3600, (rem % 3600) / 60, rem % 60);
    let (y, mo, d) = civil_from_days(days);
    format!("{y:04}-{mo:02}-{d:02} {h:02}:{m:02}:{s:02}")
}

/// 自 1970-01-01 起的天数 → (年, 月, 日)。
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// 收集事件字段：`message` 字段为日志正文，其余字段拼接到消息尾部。
#[derive(Default)]
struct MessageVisitor {
    message: Option<String>,
    fields: Vec<String>,
}

impl Visit for MessageVisitor {
    fn record_str(&mut self, field: &Field, value: &str) {
        self.record_field(field, value);
    }

    fn record_debug(&mut self, field: &Field, value: &dyn std::fmt::Debug) {
        self.record_field(field, &format!("{value:?}"));
    }

    fn record_i64(&mut self, field: &Field, value: i64) {
        self.record_field(field, &value.to_string());
    }

    fn record_u64(&mut self, field: &Field, value: u64) {
        self.record_field(field, &value.to_string());
    }

    fn record_bool(&mut self, field: &Field, value: bool) {
        self.record_field(field, &value.to_string());
    }

    fn record_f64(&mut self, field: &Field, value: f64) {
        self.record_field(field, &value.to_string());
    }

    fn record_error(&mut self, field: &Field, value: &(dyn std::error::Error + 'static)) {
        self.record_field(field, &format!("{value}"));
    }
}

impl MessageVisitor {
    fn record_field(&mut self, field: &Field, rendered: &str) {
        if field.name() == "message" {
            self.message = Some(rendered.to_string());
        } else {
            self.fields.push(format!("{}={}", field.name(), rendered));
        }
    }
}

/// 初始化日志：终端统一格式 + 缓冲采集层。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
pub fn init_tracing() {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,runtime=debug,dingda_lib=debug"));

    let _ = Registry::default()
        .with(filter)
        .with(TerminalLayer {
            lock: Mutex::new(()),
        })
        .with(LogCaptureLayer {
            buffer: buffer().clone(),
        })
        .try_init();
}
