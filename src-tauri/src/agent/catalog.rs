use super::discover::discover_agent_with_source;
use super::registry::{AgentListResponse, AgentRuntimeCatalogItem, AgentRuntimeStatusView, AGENT_REGISTRY};
use crate::runtime::RuntimeDefinition;

pub fn list_agent_runtimes() -> AgentListResponse {
    let agents = AGENT_REGISTRY.iter().map(build_catalog_item).collect();
    AgentListResponse { agents }
}

fn build_catalog_item(definition: &RuntimeDefinition) -> AgentRuntimeCatalogItem {
    let resolved = discover_agent_with_source(definition);
    let available = resolved.is_some();

    let status = if available {
        AgentRuntimeStatusView {
            state: "ready".to_string(),
            label: "已就绪".to_string(),
            hint: None,
            badge_class: "bg-emerald-500/15 text-emerald-600".to_string(),
        }
    } else {
        AgentRuntimeStatusView {
            state: "missing".to_string(),
            label: "未安装".to_string(),
            hint: None,
            badge_class: "bg-muted text-muted-foreground".to_string(),
        }
    };

    let (command, source) = match resolved {
        Some((path, src)) => (
            Some(path.display().to_string()),
            Some(src.as_str().to_string()),
        ),
        None => (None, None),
    };

    AgentRuntimeCatalogItem {
        id: definition.id.to_string(),
        name: definition.name.to_string(),
        description: definition.description.to_string(),
        available,
        version: None,
        command,
        source,
        install_url: definition.install_url.to_string(),
        docs_url: definition.docs_url.to_string(),
        is_default: definition.is_default,
        external_mcp_injection: definition.external_mcp_injection.map(str::to_string),
        status,
        can_login: definition.capabilities.login_capable,
        can_probe: true,
    }
}
