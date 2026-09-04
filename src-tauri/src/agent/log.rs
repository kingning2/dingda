//! Agent 探测与运行日志（打到壳 stderr，中文）。

use chrono::{FixedOffset, Utc};

use crate::runtime::event::AgentEvent;

const PROMPT_LOG_MAX: usize = 4000;
const STREAM_LOG_MAX: usize = 800;

/// 输出一条 Agent 相关中文日志。
pub fn log_agent(message: &str, detail: Option<&str>) {
    let prefix = "\x1b[1;32m[agent]\x1b[0m";
    let timestamp = beijing_timestamp();
    match detail {
        Some(detail) if !detail.is_empty() => {
            eprintln!("{prefix} {timestamp} {message} {detail}");
        }
        _ => eprintln!("{prefix} {timestamp} {message}"),
    }
}

/// 截断过长文本，避免把终端刷爆。
pub fn truncate_for_log(text: &str, max_chars: usize) -> String {
    let trimmed = text.trim_end();
    if trimmed.chars().count() <= max_chars {
        return trimmed.to_string();
    }
    let cut: String = trimmed.chars().take(max_chars).collect();
    format!("{cut}…（已截断）")
}

/// 记录发往 CLI 的提示词。
pub fn log_agent_prompt(prompt: &str) {
    let body = truncate_for_log(prompt, PROMPT_LOG_MAX);
    if body.is_empty() {
        log_agent("发送提示词", Some("（空）"));
        return;
    }
    // 多行时第二行起缩进，方便扫终端
    if body.contains('\n') {
        let indented = body.replace('\n', "\n           ");
        log_agent("发送提示词", Some(&format!("\n           {indented}")));
    } else {
        log_agent("发送提示词", Some(&body));
    }
}

/// 把统一 Agent 事件打成中文终端日志。
pub fn log_agent_event(event: &AgentEvent) {
    match event {
        AgentEvent::RunStarted { runtime_id, run_id } => {
            log_agent(
                "运行开始",
                Some(&format!("runtime={runtime_id} run={run_id}")),
            );
        }
        AgentEvent::TextDelta { text } => {
            let body = truncate_for_log(text, STREAM_LOG_MAX);
            if !body.is_empty() {
                log_agent("流式回复", Some(&body));
            }
        }
        AgentEvent::Thinking { text } => {
            let body = truncate_for_log(text, STREAM_LOG_MAX);
            if !body.is_empty() {
                log_agent("思考过程", Some(&body));
            }
        }
        AgentEvent::ToolCall { id, name, input } => {
            let input_text = truncate_for_log(&value_preview(input), STREAM_LOG_MAX);
            log_agent(
                "调用工具",
                Some(&format!("{name} id={id} 输入={input_text}")),
            );
        }
        AgentEvent::ToolResult { id, output } => {
            let output_text = truncate_for_log(&value_preview(output), STREAM_LOG_MAX);
            log_agent(
                "工具结果",
                Some(&format!("id={id} 输出={output_text}")),
            );
        }
        AgentEvent::FileChanged { path } => {
            log_agent("文件变更", Some(path));
        }
        AgentEvent::Session { session_id } => {
            log_agent("会话编号", Some(session_id));
        }
        AgentEvent::Error { message } => {
            log_agent("运行错误", Some(message));
        }
        AgentEvent::RunCompleted { exit_code } => {
            log_agent("运行结束", Some(&format!("退出码={exit_code}")));
        }
    }
}

/// 缓冲流式文本，攒够再打日志，减少刷屏。
pub struct StreamLogBuffer {
    text: String,
    thinking: String,
}

impl StreamLogBuffer {
    pub fn new() -> Self {
        Self {
            text: String::new(),
            thinking: String::new(),
        }
    }

    pub fn push_text(&mut self, delta: &str) {
        self.text.push_str(delta);
        if self.should_flush(&self.text, delta) {
            self.flush_text();
        }
    }

    pub fn push_thinking(&mut self, delta: &str) {
        self.thinking.push_str(delta);
        if self.should_flush(&self.thinking, delta) {
            self.flush_thinking();
        }
    }

    pub fn flush_all(&mut self) {
        self.flush_text();
        self.flush_thinking();
    }

    fn should_flush(&self, buf: &str, delta: &str) -> bool {
        buf.len() >= 120 || delta.contains('\n')
    }

    fn flush_text(&mut self) {
        if self.text.is_empty() {
            return;
        }
        log_agent_event(&AgentEvent::TextDelta {
            text: std::mem::take(&mut self.text),
        });
    }

    fn flush_thinking(&mut self) {
        if self.thinking.is_empty() {
            return;
        }
        log_agent_event(&AgentEvent::Thinking {
            text: std::mem::take(&mut self.thinking),
        });
    }
}

fn value_preview(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "null".into(),
        serde_json::Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

fn beijing_timestamp() -> String {
    let offset = FixedOffset::east_opt(8 * 3600).expect("beijing offset");
    Utc::now()
        .with_timezone(&offset)
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}
