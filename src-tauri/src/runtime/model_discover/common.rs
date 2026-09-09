use std::collections::HashSet;
use std::path::Path;

use crate::runtime::types::RuntimeModel;

pub async fn run_command(binary: &Path, args: &[&str]) -> Result<String, String> {
    let output = tokio::process::Command::new(binary)
        .args(args)
        .output()
        .await
        .map_err(|error| format!("无法执行 {}：{error}", binary.display()))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() && stdout.is_empty() {
        let detail = if !stderr.is_empty() {
            stderr
        } else {
            format!("退出码 {}", output.status.code().unwrap_or(-1))
        };
        return Err(detail);
    }

    Ok(if stdout.is_empty() { stderr } else { stdout })
}

pub fn static_models(pairs: &[(&str, &str)]) -> Vec<RuntimeModel> {
    pairs
        .iter()
        .map(|(id, label)| RuntimeModel {
            id: (*id).to_string(),
            label: (*label).to_string(),
        })
        .collect()
}

pub fn parse_codex_debug_models(stdout: &str) -> Vec<RuntimeModel> {
    let Ok(parsed) = serde_json::from_str::<serde_json::Value>(stdout) else {
        return Vec::new();
    };
    let items = parsed
        .as_array()
        .cloned()
        .or_else(|| parsed.get("models").and_then(|v| v.as_array()).cloned());
    let Some(items) = items else {
        return Vec::new();
    };

    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for raw in items {
        let Some(obj) = raw.as_object() else {
            continue;
        };
        if obj.get("visibility").and_then(|v| v.as_str()) == Some("hidden") {
            continue;
        }
        let id = obj
            .get("slug")
            .or_else(|| obj.get("id"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .to_string();
        if id.is_empty() || !seen.insert(id.clone()) {
            continue;
        }
        let label = obj
            .get("display_name")
            .or_else(|| obj.get("name"))
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .unwrap_or(&id)
            .to_string();
        out.push(RuntimeModel { id, label });
    }
    out
}

pub fn parse_opencode_models(output: &str) -> Vec<RuntimeModel> {
    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for line in output.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('{') {
            continue;
        }
        let id = line.split_whitespace().next().unwrap_or("").trim();
        if !id.contains('/') || id == id.to_uppercase() {
            continue;
        }
        if seen.insert(id.to_string()) {
            out.push(RuntimeModel {
                id: id.to_string(),
                label: id.to_string(),
            });
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_opencode_models_skips_headers() {
        let out = "PROVIDER/MODEL\nopenai/gpt-4o\nanthropic/claude-sonnet-4-6\n";
        let models = parse_opencode_models(out);
        assert_eq!(models.len(), 2);
        assert_eq!(models[0].id, "openai/gpt-4o");
    }
}
