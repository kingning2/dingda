//! Parse structured Python sidecar log lines and emit tracing events.

use std::collections::HashMap;

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct PythonLogLine {
    level: String,
    message: String,
    #[serde(default)]
    attributes: HashMap<String, serde_json::Value>,
}

pub fn emit_line(stream: &str, line: &str) {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return;
    }

    if let Ok(parsed) = serde_json::from_str::<PythonLogLine>(trimmed) {
        emit_structured(&parsed);
        return;
    }

    info!(
        target: "dingda.sidecar",
        stream,
        message = trimmed,
        "侧车日志（非结构化）"
    );
}

fn display_message(parsed: &PythonLogLine) -> String {
    let mut params: Vec<String> = parsed
        .attributes
        .iter()
        .map(|(key, value)| match value.as_str() {
            Some(s) => format!("{key}={s}"),
            None => format!("{key}={value}"),
        })
        .collect();
    params.sort();
    if params.is_empty() {
        parsed.message.clone()
    } else {
        format!("{} {}", parsed.message, params.join(" "))
    }
}

fn emit_structured(parsed: &PythonLogLine) {
    let level = parsed.level.to_ascii_uppercase();
    let message = display_message(parsed);

    match level.as_str() {
        "ERROR" | "CRITICAL" => error!(
            target: "dingda.sidecar",
            message = %message,
        ),
        "WARNING" | "WARN" => warn!(
            target: "dingda.sidecar",
            message = %message,
        ),
        "DEBUG" => debug!(
            target: "dingda.sidecar",
            message = %message,
        ),
        _ => info!(
            target: "dingda.sidecar",
            message = %message,
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_json_log_line() {
        let line = r#"{"level":"INFO","message":"侧车已启动","attributes":{"port":8787}}"#;
        let parsed: PythonLogLine = serde_json::from_str(line).unwrap();
        assert_eq!(parsed.message, "侧车已启动");
        assert_eq!(
            parsed.attributes.get("port").and_then(|v| v.as_i64()),
            Some(8787)
        );
    }

    #[test]
    fn builds_display_message_with_params() {
        let line = r#"{"level":"INFO","message":"侧车已启动","attributes":{"port":8787}}"#;
        let parsed: PythonLogLine = serde_json::from_str(line).unwrap();
        assert_eq!(display_message(&parsed), "侧车已启动 port=8787");
    }
}
