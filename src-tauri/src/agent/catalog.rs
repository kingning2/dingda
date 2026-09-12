//! 扫描本机 Agent CLI 目录（PATH / 配置路径），不做深度 probe。

use super::discover::discover_agent_with_source;
use super::registry::{
    AgentListResponse, AgentRuntimeCatalogItem, AgentRuntimeStatusView, AGENT_REGISTRY,
};
use crate::logging::{self, Scope};
use crate::runtime::RuntimeDefinition;

/// 仅返回注册表静态项（全部标为未安装），不扫 PATH。
/// 用于首次未扫描时前端占位展示。
pub fn list_agent_registry() -> AgentListResponse {
    logging::log(Scope::Agent, "加载 Agent 注册表占位", None);
    let agents: Vec<_> = AGENT_REGISTRY.iter().map(build_registry_stub).collect();
    logging::log(
        Scope::Agent,
        "Agent 注册表占位就绪",
        Some(&format!("共 {} 个", agents.len())),
    );
    AgentListResponse { agents }
}

/// 列出已注册 Agent，并标注本机是否可找到可执行文件。
pub fn list_agent_runtimes() -> AgentListResponse {
    logging::log(Scope::Agent, "开始扫描 Agent 列表", None);
    let agents: Vec<_> = AGENT_REGISTRY.iter().map(build_catalog_item).collect();
    let installed = agents.iter().filter(|item| item.available).count();
    logging::log(
        Scope::Agent,
        "Agent 列表扫描完成",
        Some(&format!("已安装 {installed} / 共 {}", agents.len())),
    );
    AgentListResponse { agents }
}

fn build_registry_stub(definition: &RuntimeDefinition) -> AgentRuntimeCatalogItem {
    AgentRuntimeCatalogItem {
        id: definition.id.to_string(),
        name: definition.name.to_string(),
        description: definition.description.to_string(),
        available: false,
        version: None,
        command: None,
        source: None,
        install_url: definition.install_url.to_string(),
        docs_url: definition.docs_url.to_string(),
        is_default: definition.is_default,
        external_mcp_injection: definition.external_mcp_injection.map(str::to_string),
        status: AgentRuntimeStatusView {
            state: "missing".to_string(),
            label: "未安装".to_string(),
            hint: Some(if definition.supports_managed_download() {
                "可点击「下载」安装到叮答托管目录".to_string()
            } else {
                "点击「扫描 Agent」检测本机是否已安装".to_string()
            }),
            badge_class: "bg-muted text-muted-foreground".to_string(),
        },
        can_login: definition.can_login(),
        can_probe: true,
        can_download: definition.supports_managed_download(),
    }
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
        Some((path, src)) => {
            logging::log(
                Scope::Agent,
                "已找到 Agent",
                Some(&format!(
                    "{} path={} source={}",
                    definition.id,
                    path.display(),
                    src.as_str()
                )),
            );
            (
                Some(path.display().to_string()),
                Some(src.as_str().to_string()),
            )
        }
        None => {
            logging::log(Scope::Agent, "未找到 Agent", Some(definition.id));
            (None, None)
        }
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
        can_login: definition.can_login(),
        can_probe: true,
        can_download: definition.supports_managed_download(),
    }
}
