//! 前端错误转发到壳终端。

use serde::Deserialize;

use crate::logging::{self, Scope};

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

/// 把前端错误打到壳 stderr（带北京时间、堆栈）。
#[tauri::command]
pub fn log_frontend_error(payload: FrontendErrorPayload) {
    logging::log(
        Scope::Frontend,
        &format!("{} {}", payload.kind, payload.message),
        None,
    );

    if let Some(source) = payload.source.as_deref() {
        let location = match (payload.lineno, payload.colno) {
            (Some(line), Some(col)) => format!("at {source}:{line}:{col}"),
            _ => format!("at {source}"),
        };
        logging::log(Scope::Frontend, &location, None);
    }

    if let Some(stack) = payload.stack.as_deref() {
        logging::log(Scope::Frontend, &format!("stack {stack}"), None);
    }
}
