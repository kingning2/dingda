use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::time::Duration;

use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command;
use tokio::time::timeout;

use crate::runtime::types::RuntimeModel;

const ACP_DEFAULT_TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Debug, Clone)]
pub struct AcpDiscoveryConfig {
    pub acp_args: Vec<String>,
    pub extra_env: Vec<(String, String)>,
    pub client_name: String,
    pub timeout: Duration,
}

impl Default for AcpDiscoveryConfig {
    fn default() -> Self {
        Self {
            acp_args: vec!["acp".to_string()],
            extra_env: Vec::new(),
            client_name: "dingda-model-discovery".to_string(),
            timeout: ACP_DEFAULT_TIMEOUT,
        }
    }
}

impl AcpDiscoveryConfig {
    pub fn with_args(args: &[&str]) -> Self {
        Self {
            acp_args: args.iter().map(|s| (*s).to_string()).collect(),
            ..Self::default()
        }
    }

    pub fn with_env(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.extra_env.push((key.into(), value.into()));
        self
    }
}

pub async fn discover_acp_models(binary: &Path, config: AcpDiscoveryConfig) -> Vec<RuntimeModel> {
    let binary = binary.to_path_buf();
    let result = timeout(config.timeout, run_acp_discovery(binary, config)).await;
    match result {
        Ok(models) => models.unwrap_or_default(),
        Err(_) => Vec::new(),
    }
}

async fn run_acp_discovery(
    binary: PathBuf,
    config: AcpDiscoveryConfig,
) -> Option<Vec<RuntimeModel>> {
    let mut cmd = Command::new(&binary);
    cmd.args(&config.acp_args)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .kill_on_drop(true);

    for (key, value) in &config.extra_env {
        cmd.env(key, value);
    }

    let mut child = cmd.spawn().ok()?;
    let mut stdin = child.stdin.take()?;
    let stdout = child.stdout.take()?;
    let mut reader = BufReader::new(stdout);

    let init_params = serde_json::json!({
        "protocolVersion": 1,
        "clientInfo": { "name": config.client_name, "version": "0.1.0" },
        "clientCapabilities": {},
    });
    request_acp(&mut reader, &mut stdin, 1, "initialize", init_params)
        .await
        .ok()?;

    let tmp = std::env::temp_dir().join(format!(
        "dingda-acp-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
    ));
    std::fs::create_dir_all(&tmp).ok()?;
    let _tmpdir_guard = TempDirGuard(tmp.clone());

    let session_params = serde_json::json!({
        "cwd": tmp.to_string_lossy(),
        "mcpServers": [],
    });
    let session_result = request_acp(&mut reader, &mut stdin, 2, "session/new", session_params)
        .await
        .ok()?;

    let _ = stdin.shutdown().await;
    let _ = child.kill().await;

    parse_acp_session_new_models(&session_result)
}

struct TempDirGuard(PathBuf);

impl Drop for TempDirGuard {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

async fn request_acp(
    reader: &mut BufReader<tokio::process::ChildStdout>,
    stdin: &mut tokio::process::ChildStdin,
    id: u64,
    method: &str,
    params: Value,
) -> Result<Value, ()> {
    let msg = serde_json::json!({
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
        "params": params,
    });
    let mut data = serde_json::to_vec(&msg).map_err(|_| ())?;
    data.push(b'\n');
    stdin.write_all(&data).await.map_err(|_| ())?;
    stdin.flush().await.map_err(|_| ())?;

    let id_str = id.to_string();
    let mut line = String::new();
    loop {
        line.clear();
        let read = reader.read_line(&mut line).await.map_err(|_| ())?;
        if read == 0 {
            return Err(());
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let env: AcpEnvelope = serde_json::from_str(trimmed).map_err(|_| ())?;
        if envelope_id(&env.id) != id_str {
            continue;
        }
        if let Some(err) = &env.error {
            if !err.is_null() {
                return Err(());
            }
        }
        return env.result.ok_or(());
    }
}

#[derive(serde::Deserialize)]
struct AcpEnvelope {
    id: Value,
    result: Option<Value>,
    error: Option<Value>,
}

fn envelope_id(id: &Value) -> String {
    match id {
        Value::Number(n) => n.to_string(),
        Value::String(s) => s.clone(),
        _ => id.to_string(),
    }
}

pub fn parse_acp_session_new_models(raw: &Value) -> Option<Vec<RuntimeModel>> {
    if let Some(models) = parse_acp_models_block(raw) {
        if !models.is_empty() {
            return Some(models);
        }
    }
    parse_acp_config_option_models(raw)
}

fn parse_acp_models_block(raw: &Value) -> Option<Vec<RuntimeModel>> {
    let models = raw.get("models")?;
    let available = models
        .get("availableModels")
        .or_else(|| models.get("available_models"))?
        .as_array()?;
    let current = models
        .get("currentModelId")
        .or_else(|| models.get("current_model_id"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();

    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for entry in available {
        let id = entry
            .get("modelId")
            .or_else(|| entry.get("model_id"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .to_string();
        if id.is_empty() || !seen.insert(id.clone()) {
            continue;
        }
        let name = entry
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim();
        let label = acp_model_label(name, &id);
        out.push(RuntimeModel {
            id: id.clone(),
            label: if id == current {
                format!("{label} (current)")
            } else {
                label
            },
        });
    }
    if out.is_empty() {
        None
    } else {
        Some(out)
    }
}

fn parse_acp_config_option_models(raw: &Value) -> Option<Vec<RuntimeModel>> {
    let options = raw
        .get("configOptions")
        .or_else(|| raw.get("config_options"))
        .and_then(|v| v.as_array())?;

    for opt in options {
        let id = opt.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let category = opt.get("category").and_then(|v| v.as_str()).unwrap_or("");
        if !id.eq_ignore_ascii_case("model") && !category.eq_ignore_ascii_case("model") {
            continue;
        }
        let current = opt
            .get("currentValue")
            .or_else(|| opt.get("current_value"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .to_string();
        let choices = opt.get("options").and_then(|v| v.as_array())?;
        let mut out = Vec::new();
        let mut seen = HashSet::new();
        for choice in choices {
            let model_id = choice
                .get("value")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim()
                .to_string();
            if model_id.is_empty() || !seen.insert(model_id.clone()) {
                continue;
            }
            let name = choice
                .get("name")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim();
            let label = acp_model_label(name, &model_id);
            out.push(RuntimeModel {
                id: model_id.clone(),
                label: if model_id == current {
                    format!("{label} (current)")
                } else {
                    label
                },
            });
        }
        if !out.is_empty() {
            return Some(out);
        }
    }
    None
}

fn acp_model_label(name: &str, model_id: &str) -> String {
    let label = name.trim();
    if label.is_empty() || label.eq_ignore_ascii_case("unknown") {
        model_id.to_string()
    } else {
        label.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_acp_models_block_reads_available_models() {
        let raw = json!({
            "models": {
                "availableModels": [
                    {"modelId": "gpt-5", "name": "GPT-5"},
                    {"modelId": "claude-sonnet", "name": "Claude Sonnet"}
                ],
                "currentModelId": "gpt-5"
            }
        });
        let models = parse_acp_session_new_models(&raw).unwrap();
        assert_eq!(models.len(), 2);
        assert!(models[0].label.contains("current"));
    }

    #[test]
    fn parse_acp_config_option_models_reads_model_select() {
        let raw = json!({
            "configOptions": [{
                "id": "model",
                "currentValue": "kimi-code/k3",
                "options": [
                    {"value": "kimi-code/k3", "name": "K3"},
                    {"value": "kimi-code/k2", "name": "K2"}
                ]
            }]
        });
        let models = parse_acp_session_new_models(&raw).unwrap();
        assert_eq!(models.len(), 2);
        assert_eq!(models[0].id, "kimi-code/k3");
    }
}
