use std::path::Path;

use tokio::process::Command;

use super::discover::discover_agent;
use super::registry::find_agent;
use crate::runtime::detection::detect_runtime;
use crate::runtime::{RuntimeDefinition, types::RuntimeModel};

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentRuntimeProbeResult {
    pub available: bool,
    pub version: Option<String>,
    pub command: Option<String>,
    pub source: Option<String>,
    pub authenticated: Option<bool>,
    pub models: Option<Vec<RuntimeModel>>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentRuntimeLoginResult {
    pub started: bool,
    pub message: String,
}

pub async fn probe_agent(definition: &RuntimeDefinition) -> AgentRuntimeProbeResult {
    let detection = detect_runtime(definition).await;

    if !detection.available {
        return AgentRuntimeProbeResult {
            available: false,
            version: detection.version,
            command: detection.executable,
            source: detection.source.map(|s| s.as_str().to_string()),
            authenticated: detection.authenticated,
            models: None,
            error: detection.error,
        };
    }

    let command = detection.executable.clone();
    let binary = command.as_ref().map(Path::new);

    let models = if let Some(binary) = binary {
        let models = (definition.discover_models)(binary).await;
        if models.is_empty() {
            None
        } else {
            Some(models)
        }
    } else {
        None
    };

    AgentRuntimeProbeResult {
        available: true,
        version: detection.version,
        command,
        source: detection.source.map(|s| s.as_str().to_string()),
        authenticated: detection.authenticated,
        models,
        error: None,
    }
}

pub async fn probe_agent_by_id(agent_id: &str) -> Result<AgentRuntimeProbeResult, String> {
    let definition = find_agent(agent_id).ok_or_else(|| format!("未知 Agent：{agent_id}"))?;
    Ok(probe_agent(definition).await)
}

pub async fn login_agent_by_id(agent_id: &str) -> Result<AgentRuntimeLoginResult, String> {
    let definition = find_agent(agent_id).ok_or_else(|| format!("未知 Agent：{agent_id}"))?;
    if !definition.capabilities.login_capable {
        return Err(format!("暂不支持登录 Agent：{agent_id}"));
    }
    login_codex().await
}

pub async fn login_codex() -> Result<AgentRuntimeLoginResult, String> {
    let definition = find_agent("codex").ok_or("未知 Agent：codex")?;
    let binary = discover_agent(definition)
        .ok_or_else(|| "未找到 codex，请先按官方文档安装".to_string())?;

    Command::new(&binary)
        .args(["login"])
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .spawn()
        .map_err(|error| format!("无法启动 codex login：{error}"))?;

    Ok(AgentRuntimeLoginResult {
        started: true,
        message: "已在浏览器中打开 Codex 登录页，完成后请点击「扫描 Agent」刷新状态。".to_string(),
    })
}
