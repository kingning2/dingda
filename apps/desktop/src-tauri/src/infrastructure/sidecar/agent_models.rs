//! 从 AI 配置解析节点模型载荷。

use crate::contracts::{
    AgentSidecarNodeModel, AiAccount, AiGraphModels, AiIpcConfigResponse, AiProvider,
};

/// 无账号平台（如 Ollama）在任务上的 id 前缀。
pub const PROVIDER_ACCOUNT_PREFIX: &str = "provider:";

#[derive(Debug, Clone)]
pub struct ResolvedModel {
    pub account_id: String,
    pub base_url: String,
    pub api_key: String,
    pub model: String,
    pub provider_type: String,
}

impl ResolvedModel {
    pub fn to_sidecar(&self, node: &str) -> AgentSidecarNodeModel {
        AgentSidecarNodeModel {
            node: node.to_string(),
            account_id: Some(self.account_id.clone()),
            base_url: self.base_url.clone(),
            api_key: self.api_key.clone(),
            model: self.model.clone(),
            provider_type: Some(self.provider_type.clone()),
        }
    }
}

pub fn resolve_account(
    config: &AiIpcConfigResponse,
    account_id: &str,
) -> Result<ResolvedModel, String> {
    let selected = account_id.trim();
    if selected.is_empty() {
        return Err("account_id 为空".to_string());
    }
    if let Some(provider_id) = selected.strip_prefix(PROVIDER_ACCOUNT_PREFIX) {
        let provider = config
            .providers
            .iter()
            .find(|item| item.id == provider_id)
            .ok_or_else(|| format!("AI 平台 {provider_id} 不存在"))?;
        return Ok(authless(provider, selected));
    }
    let account = config
        .accounts
        .iter()
        .find(|item| item.id == selected)
        .ok_or_else(|| format!("AI 账号 {selected} 不存在"))?;
    let provider = config
        .providers
        .iter()
        .find(|item| item.id == account.provider_id)
        .ok_or_else(|| format!("账号 {} 的平台不存在", account.id))?;
    Ok(from_account(provider, account))
}

fn authless(provider: &AiProvider, account_id: &str) -> ResolvedModel {
    let model = provider
        .default_model
        .clone()
        .unwrap_or_else(|| "default".to_string());
    let base_url = provider.base_url.clone().unwrap_or_default();
    ResolvedModel {
        account_id: account_id.to_string(),
        base_url,
        api_key: String::new(),
        model,
        provider_type: provider.kind.clone(),
    }
}

fn from_account(provider: &AiProvider, account: &AiAccount) -> ResolvedModel {
    let model = account
        .default_model
        .clone()
        .or_else(|| provider.default_model.clone())
        .unwrap_or_else(|| "default".to_string());
    let base_url = provider.base_url.clone().unwrap_or_default();
    ResolvedModel {
        account_id: account.id.clone(),
        base_url,
        api_key: account.api_key.clone(),
        model,
        provider_type: provider.kind.clone(),
    }
}

/// 为比价 AI 节点构建 node_models；无账号节点不出现在列表中。
pub fn build_node_models(
    config: &AiIpcConfigResponse,
    graph: Option<&AiGraphModels>,
) -> Result<(Vec<AgentSidecarNodeModel>, Option<ResolvedModel>), String> {
    const AI_NODES: &[&str] = &[
        "web_research",
        "article_analyze",
        "planner",
        "analyze",
        "finalize",
    ];
    let mut node_models = Vec::new();
    let mut default_model: Option<ResolvedModel> = None;

    let node_accounts = graph.and_then(|g| g.node_accounts.as_ref());
    for node in AI_NODES {
        let account_id = node_accounts
            .and_then(|rows| {
                rows.iter()
                    .find(|row| row.node == *node)
                    .map(|row| row.account_id.clone())
            })
            .or_else(|| config.accounts.first().map(|a| a.id.clone()))
            .unwrap_or_default();
        if account_id.is_empty() {
            continue;
        }
        let resolved = resolve_account(config, &account_id)?;
        if default_model.is_none() {
            default_model = Some(resolved.clone());
        }
        node_models.push(resolved.to_sidecar(node));
    }

    // If no per-node mapping but have any account, use first as default for all AI nodes
    if node_models.is_empty() {
        if let Some(account) = config.accounts.first() {
            let resolved = resolve_account(config, &account.id)?;
            default_model = Some(resolved.clone());
            for node in AI_NODES {
                node_models.push(resolved.to_sidecar(node));
            }
        }
    }

    Ok((node_models, default_model))
}

pub fn failover_account_ids(graph: Option<&AiGraphModels>) -> (bool, Vec<String>) {
    let enabled = graph.and_then(|g| g.failover_enabled).unwrap_or(true);
    let ids = graph
        .and_then(|g| g.failover_account_ids.clone())
        .unwrap_or_default();
    (enabled, ids)
}
