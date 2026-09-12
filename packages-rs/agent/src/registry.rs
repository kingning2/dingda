use serde::Serialize;

use runtime::{find_runtime, RuntimeDefinition, RUNTIME_REGISTRY};

pub const AGENT_REGISTRY: &[RuntimeDefinition] = RUNTIME_REGISTRY;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentRuntimeStatusView {
    pub state: String,
    pub label: String,
    pub hint: Option<String>,
    pub badge_class: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentRuntimeCatalogItem {
    pub id: String,
    pub name: String,
    pub description: String,
    pub available: bool,
    pub version: Option<String>,
    pub command: Option<String>,
    pub source: Option<String>,
    pub install_url: String,
    pub docs_url: String,
    pub is_default: bool,
    pub external_mcp_injection: Option<String>,
    pub status: AgentRuntimeStatusView,
    pub can_login: bool,
    pub can_probe: bool,
    /// 是否支持叮答托管一键下载。
    pub can_download: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentListResponse {
    pub agents: Vec<AgentRuntimeCatalogItem>,
}

pub fn find_agent(agent_id: &str) -> Option<&'static RuntimeDefinition> {
    find_runtime(agent_id)
}
