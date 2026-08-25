//! 闲鱼监控 AI — 关键词生成与商品决策（Rust LLM + 余额不足自动切换）。

use agent::{
    inject_web_context, normalize_provider_type, provider_from_settings, run_tool_loop,
    ChatMessage, ChatRequest, ProviderSettings, ToolLoopConfig, ToolTraceEntry, WebSearchBundle,
};
use common::contracts::{AiAccount, AiIpcConfigResponse, AiProvider};
use serde::Deserialize;
use std::collections::HashSet;
use tracing::warn;

/// 无账号平台（如 Ollama）在任务上的 id 前缀。
pub const PROVIDER_ACCOUNT_PREFIX: &str = "provider:";

#[derive(Debug, Clone, Deserialize)]
pub struct MonitorAiDecision {
    pub recommended: bool,
    pub reason: String,
}

/// 关键词生成结果（含 AI 原始返回，供转录展示）。
pub struct KeywordGenResult {
    pub keywords: Vec<String>,
    pub raw: String,
    pub tool_trace: Vec<ToolTraceEntry>,
}

/// 单条商品决策结果（含 AI 原始返回，供转录展示）。
pub struct DecideResult {
    pub decision: MonitorAiDecision,
    pub raw: String,
    pub tool_trace: Vec<ToolTraceEntry>,
}

/// 单次任务运行内的 AI 账号切换上下文（成功后 sticky，避免每条商品重试已失败的账号）。
#[derive(Debug, Clone)]
pub struct AiFailoverContext {
    primary_id: String,
    failover_enabled: bool,
    account_order: Vec<String>,
    sticky_id: Option<String>,
}

impl AiFailoverContext {
    pub fn new(primary_id: &str, failover_enabled: bool, account_order: Vec<String>) -> Self {
        Self {
            primary_id: primary_id.trim().to_string(),
            failover_enabled,
            account_order,
            sticky_id: None,
        }
    }
}

pub fn resolve_provider_settings(
    config: &AiIpcConfigResponse,
    ai_account_id: &str,
) -> Result<ProviderSettings, String> {
    let selected = ai_account_id.trim();
    if let Some(provider_id) = selected.strip_prefix(PROVIDER_ACCOUNT_PREFIX) {
        let provider = config
            .providers
            .iter()
            .find(|item| item.id == provider_id)
            .ok_or_else(|| format!("AI 平台 {provider_id} 不存在"))?;
        return Ok(build_authless_provider_settings(provider));
    }

    let account = if selected.is_empty() {
        config
            .accounts
            .first()
            .ok_or_else(|| "请先在设置中配置 AI 账号，或在任务中选择 AI 账号".to_string())?
    } else {
        config
            .accounts
            .iter()
            .find(|item| item.id == selected)
            .ok_or_else(|| "所选 AI 账号不存在，请在任务中重新选择".to_string())?
    };

    let provider = config
        .providers
        .iter()
        .find(|item| item.id == account.provider_id)
        .ok_or_else(|| "AI 账号关联的 Provider 不存在".to_string())?;
    Ok(build_provider_settings(account, provider))
}

/// 候选 AI 账号顺序。
///
/// - 关闭 failover：仅 sticky / 首选
/// - 配置了 `account_order`：sticky → 首选 → 自定义顺序（仅有效 id）
/// - 否则：sticky → 首选 → 其余云账号 → 无账号平台（Ollama）
pub fn list_ai_account_candidates(
    config: &AiIpcConfigResponse,
    primary: &str,
    sticky: Option<&str>,
    failover_enabled: bool,
    account_order: &[String],
) -> Vec<String> {
    let primary = primary.trim();
    if !failover_enabled {
        let id = sticky.unwrap_or(primary).trim();
        return if id.is_empty() {
            Vec::new()
        } else {
            vec![id.to_string()]
        };
    }

    let mut seen = HashSet::new();
    let mut out = Vec::new();

    let mut push = |id: &str| {
        let id = id.trim();
        if id.is_empty() || !is_known_ai_account_id(config, id) || !seen.insert(id.to_string()) {
            return;
        }
        out.push(id.to_string());
    };

    if let Some(id) = sticky {
        push(id);
    }
    push(primary);

    if !account_order.is_empty() {
        for id in account_order {
            push(id);
        }
        return out;
    }

    for account in &config.accounts {
        push(&account.id);
    }
    for provider in authless_provider_ids(config) {
        push(&provider);
    }

    out
}

fn is_known_ai_account_id(config: &AiIpcConfigResponse, id: &str) -> bool {
    if id.starts_with(PROVIDER_ACCOUNT_PREFIX) {
        let provider_id = id.trim_start_matches(PROVIDER_ACCOUNT_PREFIX);
        return config.providers.iter().any(|item| item.id == provider_id);
    }
    config.accounts.iter().any(|item| item.id == id)
}

fn authless_provider_ids(config: &AiIpcConfigResponse) -> Vec<String> {
    config
        .providers
        .iter()
        .filter(|provider| {
            !config
                .accounts
                .iter()
                .any(|account| account.provider_id == provider.id)
        })
        .map(|provider| format!("{PROVIDER_ACCOUNT_PREFIX}{}", provider.id))
        .collect()
}

fn build_authless_provider_settings(provider: &AiProvider) -> ProviderSettings {
    let base_url = provider.base_url.clone().unwrap_or_default();
    let model = provider
        .default_model
        .clone()
        .unwrap_or_else(|| "qwen2.5".to_string());
    ProviderSettings {
        provider_type: normalize_provider_type(&provider.kind, &base_url, &model),
        api_key: String::new(),
        base_url,
        model,
    }
}

fn build_provider_settings(account: &AiAccount, provider: &AiProvider) -> ProviderSettings {
    let base_url = provider.base_url.clone().unwrap_or_default();
    let model = account
        .default_model
        .clone()
        .or_else(|| provider.default_model.clone())
        .unwrap_or_else(|| "qwen-plus".to_string());
    ProviderSettings {
        provider_type: normalize_provider_type(&provider.kind, &base_url, &model),
        api_key: account.api_key.clone(),
        base_url,
        model,
    }
}

pub fn build_keyword_prompt(intent: &str, criteria: &str) -> String {
    format!(
        "你是闲鱼二手商品监控助手。根据用户购买意图生成 1~5 个适合在闲鱼搜索的关键词。\n\
         要求：只输出 JSON 数组，如 [\"关键词1\",\"关键词2\"]，不要其它文字。\n\
         用户意图：{intent}\n\
         筛选标准：{criteria}"
    )
}

pub async fn generate_keywords(
    config: &AiIpcConfigResponse,
    failover: &mut AiFailoverContext,
    prompt: &str,
) -> Result<KeywordGenResult, String> {
    let completed = complete_json_with_failover(config, failover, prompt).await?;
    let parsed: Vec<String> = serde_json::from_str(&extract_json_array(&completed.raw))
        .map_err(|error| format!("AI 关键词 JSON 解析失败: {error}; raw={}", completed.raw))?;
    let keywords: Vec<String> = parsed
        .into_iter()
        .map(|item| item.trim().to_string())
        .filter(|item| !item.is_empty())
        .collect();
    if keywords.is_empty() {
        return Err("AI 未生成有效关键词".to_string());
    }
    Ok(KeywordGenResult {
        keywords,
        raw: completed.raw,
        tool_trace: completed.tool_trace,
    })
}

pub fn build_decision_prompt(criteria: &str, item_json: &str) -> String {
    format!(
        "你是闲鱼捡漏助手。根据筛选标准判断商品是否值得通知用户。\n\
         只输出 JSON：{{\"recommended\": true/false, \"reason\": \"一句话理由\"}}\n\
         筛选标准：{criteria}\n\
         商品信息：{item_json}"
    )
}

pub async fn decide_item(
    config: &AiIpcConfigResponse,
    failover: &mut AiFailoverContext,
    prompt: &str,
) -> Result<DecideResult, String> {
    let completed = complete_json_with_failover(config, failover, prompt).await?;
    let json_text = extract_json_object(&completed.raw);
    let decision = serde_json::from_str(&json_text)
        .map_err(|error| format!("AI 决策 JSON 解析失败: {error}; raw={}", completed.raw))?;
    Ok(DecideResult {
        decision,
        raw: completed.raw,
        tool_trace: completed.tool_trace,
    })
}

/// 是否启用监控 AI 联网搜索（默认开；`DINGDA_MONITOR_WEB_SEARCH=0` 关闭）。
pub fn monitor_web_search_enabled() -> bool {
    match std::env::var("DINGDA_MONITOR_WEB_SEARCH") {
        Ok(value) => {
            let v = value.trim().to_lowercase();
            !matches!(v.as_str(), "0" | "false" | "off" | "no")
        }
        Err(_) => true,
    }
}

/// 非 tool-loop 回退：用意图/标准拼一次搜索（失败则跳过）。
async fn fetch_monitor_web_context_raw(prompt: &str) -> Option<String> {
    let query = prompt.chars().take(80).collect::<String>();
    if query.trim().is_empty() {
        return None;
    }
    let bundle = WebSearchBundle::default_bundle();
    let result = bundle.search(&query).await;
    if result.is_error {
        warn!(error = %result.content, "监控联网搜索回退失败（已跳过）");
        return None;
    }
    Some(result.content)
}

struct CompletedJson {
    raw: String,
    tool_trace: Vec<ToolTraceEntry>,
}

async fn complete_json_with_failover(
    config: &AiIpcConfigResponse,
    failover: &mut AiFailoverContext,
    prompt: &str,
) -> Result<CompletedJson, String> {
    let candidates = list_ai_account_candidates(
        config,
        &failover.primary_id,
        failover.sticky_id.as_deref(),
        failover.failover_enabled,
        &failover.account_order,
    );
    if candidates.is_empty() {
        return Err("没有可用的 AI 账号".to_string());
    }

    let mut last_error = String::new();
    for (index, account_id) in candidates.iter().enumerate() {
        let settings = match resolve_provider_settings(config, account_id) {
            Ok(value) => value,
            Err(error) => {
                last_error = error;
                continue;
            }
        };

        match complete_json(&settings, prompt).await {
            Ok(value) => {
                if index > 0 {
                    warn!(
                        primary = %failover.primary_id,
                        fallback = %account_id,
                        "AI 调用失败后已自动切换账号"
                    );
                }
                failover.sticky_id = Some(account_id.clone());
                return Ok(value);
            }
            Err(error) => {
                last_error = error.clone();
                let has_next = index + 1 < candidates.len();
                if has_next && failover.failover_enabled && is_retryable_ai_error(&error) {
                    warn!(account_id = %account_id, %error, "AI 调用失败，尝试下一个账号");
                    continue;
                }
                return Err(error);
            }
        }
    }

    Err(if last_error.is_empty() {
        "所有 AI 账号均不可用".to_string()
    } else {
        last_error
    })
}

const TOOL_LOOP_HINT: &str = "\n\n你可以使用 web_search 工具查询公开网页上的行情/参考信息。\
最终只输出任务要求的 JSON，不要输出其它说明文字。";

async fn complete_json(settings: &ProviderSettings, prompt: &str) -> Result<CompletedJson, String> {
    let provider = provider_from_settings(settings).map_err(|error| error.to_string())?;

    if provider.supports_tools() && monitor_web_search_enabled() {
        let bundle = WebSearchBundle::default_bundle();
        let request = ChatRequest {
            model: settings.model.clone(),
            messages: vec![
                ChatMessage::system(TOOL_LOOP_HINT.trim()),
                ChatMessage::user(prompt),
            ],
            max_tokens: 768,
            temperature: 0.2,
            disable_thinking: true,
            ..Default::default()
        };
        let outcome = run_tool_loop(
            provider.as_ref(),
            &bundle.tools,
            request,
            ToolLoopConfig {
                max_rounds: 4,
                tool_choice: Some("auto".into()),
            },
        )
        .await
        .map_err(|error| error.to_string())?;
        return Ok(CompletedJson {
            raw: outcome.reply.trim().to_string(),
            tool_trace: outcome.tool_trace,
        });
    }

    // 非 OpenAI-compatible：可选预搜索注入后单次 complete。
    let prompt = if monitor_web_search_enabled() {
        match fetch_monitor_web_context_raw(prompt).await {
            Some(ctx) => inject_web_context(prompt, &ctx),
            None => prompt.to_string(),
        }
    } else {
        prompt.to_string()
    };

    let response = provider
        .complete(&ChatRequest {
            model: settings.model.clone(),
            messages: vec![ChatMessage::user(prompt)],
            max_tokens: 512,
            temperature: 0.2,
            disable_thinking: true,
            ..Default::default()
        })
        .await
        .map_err(|error| error.to_string())?;
    Ok(CompletedJson {
        raw: response.reply.trim().to_string(),
        tool_trace: Vec::new(),
    })
}

/// 余额不足、配额耗尽、限流等可切换账号重试的错误。
fn is_retryable_ai_error(message: &str) -> bool {
    let lower = message.to_lowercase();
    [
        "402",
        "429",
        "403",
        "insufficient",
        "balance",
        "quota",
        "credit",
        "billing",
        "payment required",
        "exceeded",
        "rate limit",
        "ratelimit",
        "too many requests",
        "余额",
        "不足",
        "欠费",
        "额度",
    ]
    .iter()
    .any(|needle| lower.contains(needle))
}

fn extract_json_array(raw: &str) -> String {
    if let (Some(start), Some(end)) = (raw.find('['), raw.rfind(']')) {
        if start <= end {
            return raw[start..=end].to_string();
        }
    }
    raw.to_string()
}

fn extract_json_object(raw: &str) -> String {
    if let (Some(start), Some(end)) = (raw.find('{'), raw.rfind('}')) {
        if start <= end {
            return raw[start..=end].to_string();
        }
    }
    raw.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_api_key(suffix: &str) -> String {
        format!("fixture-{suffix}")
    }

    #[test]
    fn detects_retryable_balance_errors() {
        assert!(is_retryable_ai_error("402 Payment Required"));
        assert!(is_retryable_ai_error("Insufficient Balance"));
        assert!(is_retryable_ai_error("余额不足，请充值"));
        assert!(is_retryable_ai_error("429 Too Many Requests"));
        assert!(!is_retryable_ai_error("invalid json payload"));
    }

    #[test]
    fn candidate_order_prefers_sticky_then_primary() {
        let config = AiIpcConfigResponse {
            providers: vec![AiProvider {
                id: "ollama".to_string(),
                kind: "openai-compatible".to_string(),
                name: "Ollama".to_string(),
                base_url: Some("http://localhost:11434/v1".to_string()),
                default_model: None,
            }],
            accounts: vec![
                AiAccount {
                    id: "acc-a".to_string(),
                    provider_id: "deepseek".to_string(),
                    name: "A".to_string(),
                    api_key: fixture_api_key("a"),
                    default_model: None,
                },
                AiAccount {
                    id: "acc-b".to_string(),
                    provider_id: "doubao".to_string(),
                    name: "B".to_string(),
                    api_key: fixture_api_key("b"),
                    default_model: None,
                },
            ],
        };
        let ids = list_ai_account_candidates(&config, "acc-a", Some("acc-b"), true, &[]);
        assert_eq!(ids, vec!["acc-b", "acc-a", "provider:ollama"]);
    }

    #[test]
    fn failover_disabled_only_uses_primary() {
        let config = AiIpcConfigResponse {
            providers: vec![],
            accounts: vec![AiAccount {
                id: "acc-a".to_string(),
                provider_id: "deepseek".to_string(),
                name: "A".to_string(),
                api_key: fixture_api_key("solo"),
                default_model: None,
            }],
        };
        let ids = list_ai_account_candidates(&config, "acc-a", None, false, &[]);
        assert_eq!(ids, vec!["acc-a"]);
    }

    #[test]
    fn custom_order_limits_failover_sequence() {
        let config = AiIpcConfigResponse {
            providers: vec![],
            accounts: vec![
                AiAccount {
                    id: "acc-a".to_string(),
                    provider_id: "deepseek".to_string(),
                    name: "A".to_string(),
                    api_key: fixture_api_key("a"),
                    default_model: None,
                },
                AiAccount {
                    id: "acc-b".to_string(),
                    provider_id: "doubao".to_string(),
                    name: "B".to_string(),
                    api_key: fixture_api_key("b"),
                    default_model: None,
                },
                AiAccount {
                    id: "acc-c".to_string(),
                    provider_id: "doubao".to_string(),
                    name: "C".to_string(),
                    api_key: fixture_api_key("c"),
                    default_model: None,
                },
            ],
        };
        let ids = list_ai_account_candidates(
            &config,
            "acc-a",
            None,
            true,
            &["acc-c".to_string(), "acc-b".to_string()],
        );
        assert_eq!(ids, vec!["acc-a", "acc-c", "acc-b"]);
    }
}
