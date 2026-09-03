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

pub fn parse_cursor_models(output: &str) -> Vec<RuntimeModel> {
    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for line in output.lines() {
        let line = line.trim();
        let Some((id, label)) = line.split_once(" - ") else {
            continue;
        };
        let id = id.trim();
        let mut label = label.trim().to_string();
        if id.is_empty() || !seen.insert(id.to_string()) {
            continue;
        }
        for suffix in [" (current, default)", " (default)", " (current)"] {
            label = label.replace(suffix, "");
        }
        out.push(RuntimeModel {
            id: id.to_string(),
            label: if label.is_empty() { id.to_string() } else { label },
        });
    }
    out
}

pub fn parse_pi_models(output: &str) -> Vec<RuntimeModel> {
    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for line in output.lines() {
        let line = line.trim();
        if line.is_empty() || is_pi_discovery_noise(line) {
            continue;
        }
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.is_empty() {
            continue;
        }
        if fields[0].eq_ignore_ascii_case("provider") {
            continue;
        }
        let id = if fields[0].contains(':') || fields[0].contains('/') {
            fields[0].replace(':', "/")
        } else if fields.len() >= 2 {
            format!("{}/{}", fields[0], fields[1])
        } else {
            continue;
        };
        let slash = id.find('/').unwrap_or(0);
        if slash == 0 || slash == id.len() - 1 {
            continue;
        }
        if seen.insert(id.clone()) {
            out.push(RuntimeModel {
                id: id.clone(),
                label: id,
            });
        }
    }
    out
}

fn is_pi_discovery_noise(line: &str) -> bool {
    let lower = line.to_ascii_lowercase();
    lower.starts_with("warning:")
        || lower.starts_with("error:")
        || lower.starts_with("note:")
        || lower.starts_with("hint:")
}

pub fn parse_id_label_lines(output: &str) -> Vec<RuntimeModel> {
    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for line in output.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let (id, label) = if let Some((id, label)) = line.split_once(" - ") {
            (id.trim(), label.trim())
        } else if let Some((id, label)) = line.split_once('\t') {
            (id.trim(), label.trim())
        } else {
            continue;
        };
        if id.is_empty() || !seen.insert(id.to_string()) {
            continue;
        }
        out.push(RuntimeModel {
            id: id.to_string(),
            label: if label.is_empty() {
                id.to_string()
            } else {
                label.to_string()
            },
        });
    }
    out
}

pub fn parse_plain_id_lines(output: &str) -> Vec<RuntimeModel> {
    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for line in output.lines() {
        let id = line.trim();
        if id.is_empty() || id.starts_with('#') || !seen.insert(id.to_string()) {
            continue;
        }
        out.push(RuntimeModel {
            id: id.to_string(),
            label: id.to_string(),
        });
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

    #[test]
    fn parse_cursor_models_parses_id_label_rows() {
        let out = "Available models\n\nauto - Auto\ncomposer-2 - Composer 2 (default)\n";
        let models = parse_cursor_models(out);
        assert_eq!(models.len(), 2);
        assert_eq!(models[1].id, "composer-2");
    }

    #[test]
    fn parse_pi_models_normalizes_provider_model_table() {
        let out = "provider model\nopenai gpt-4o\nanthropic claude-sonnet\n";
        let models = parse_pi_models(out);
        assert_eq!(models.len(), 2);
        assert_eq!(models[0].id, "openai/gpt-4o");
    }
}
