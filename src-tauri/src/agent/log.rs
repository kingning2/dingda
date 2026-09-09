//! Agent 探测日志（打到壳 stderr，中文）。

use chrono::{FixedOffset, Utc};

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

fn beijing_timestamp() -> String {
    let offset = FixedOffset::east_opt(8 * 3600).expect("beijing offset");
    Utc::now()
        .with_timezone(&offset)
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}
