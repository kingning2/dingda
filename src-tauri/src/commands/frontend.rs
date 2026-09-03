use chrono::{FixedOffset, TimeZone, Utc};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FrontendErrorPayload {
    pub kind: String,
    pub message: String,
    pub source: Option<String>,
    pub lineno: Option<u32>,
    pub colno: Option<u32>,
    pub stack: Option<String>,
}

#[tauri::command]
pub fn log_frontend_error(payload: FrontendErrorPayload) {
    let prefix = "\x1b[1;35m[frontend]\x1b[0m";
    let timestamp = FixedOffset::east_opt(8 * 3600)
        .expect("beijing offset")
        .from_utc_datetime(&Utc::now().naive_utc())
        .format("%Y-%m-%d %H:%M:%S")
        .to_string();

    eprintln!(
        "{prefix} {timestamp} {} {}",
        payload.kind, payload.message
    );

    if let Some(source) = payload.source.as_deref() {
        match (payload.lineno, payload.colno) {
            (Some(line), Some(col)) => eprintln!("{prefix} {timestamp} at {source}:{line}:{col}"),
            _ => eprintln!("{prefix} {timestamp} at {source}"),
        }
    }

    if let Some(stack) = payload.stack.as_deref() {
        eprintln!("{prefix} {timestamp} stack {stack}");
    }
}
