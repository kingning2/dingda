//! model crate — LLM 模型家族（**自包含**，只依赖外部 crate）。
//!
//! - 根 — 模型 **seam**：`LlmProvider` trait + 类型 + 错误 + [`provider_from_settings`] 工厂
//! - `openai` / `anthropic` / `gemini` / `dashscope` — LLM provider 模块
//!
//! 由 `agent`（编排层）消费，不依赖任何其它 DingDa crate。

pub mod anthropic;
pub mod dashscope;
pub mod gemini;
pub mod openai;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

/// LLM 调用错误。
#[derive(Debug, Error)]
pub enum LlmError {
    #[error("llm provider error: {0}")]
    Provider(String),
    #[error("llm transport error: {0}")]
    Transport(String),
    #[error("llm empty response")]
    EmptyResponse,
    #[error("tool loop exceeded max rounds ({0})")]
    ToolLoopExhausted(usize),
}

/// 模型发起的一次函数调用（OpenAI `tool_calls[]` 语义）。
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AssistantToolCall {
    pub id: String,
    pub name: String,
    /// 模型返回的原始 JSON 字符串（可能非法，执行前再解析）。
    pub arguments: String,
}

/// 注册给模型的工具规格（OpenAI `tools[].function`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub parameters: Value,
}

/// 对话消息（支持 tool_calls / tool 回填）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    #[serde(default)]
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_calls: Option<Vec<AssistantToolCall>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
}

impl ChatMessage {
    pub fn system(content: impl Into<String>) -> Self {
        Self {
            role: "system".to_string(),
            content: content.into(),
            tool_calls: None,
            tool_call_id: None,
        }
    }

    pub fn user(content: impl Into<String>) -> Self {
        Self {
            role: "user".to_string(),
            content: content.into(),
            tool_calls: None,
            tool_call_id: None,
        }
    }

    pub fn assistant(content: impl Into<String>) -> Self {
        Self {
            role: "assistant".to_string(),
            content: content.into(),
            tool_calls: None,
            tool_call_id: None,
        }
    }

    pub fn assistant_tools(content: impl Into<String>, tool_calls: Vec<AssistantToolCall>) -> Self {
        Self {
            role: "assistant".to_string(),
            content: content.into(),
            tool_calls: Some(tool_calls),
            tool_call_id: None,
        }
    }

    pub fn tool(tool_call_id: impl Into<String>, content: impl Into<String>) -> Self {
        Self {
            role: "tool".to_string(),
            content: content.into(),
            tool_calls: None,
            tool_call_id: Some(tool_call_id.into()),
        }
    }
}

/// 补全请求。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    pub max_tokens: u32,
    pub temperature: f32,
    /// 是否禁用思考（部分模型支持）。
    pub disable_thinking: bool,
    /// OpenAI-compatible function tools；`None` 表示不下发。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tools: Option<Vec<ToolSpec>>,
    /// `auto` / `none` / 或具体工具名；`None` 表示由服务端默认。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_choice: Option<String>,
}

impl Default for ChatRequest {
    fn default() -> Self {
        Self {
            model: String::new(),
            messages: Vec::new(),
            max_tokens: 512,
            temperature: 0.2,
            disable_thinking: false,
            tools: None,
            tool_choice: None,
        }
    }
}

/// 补全响应。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatResponse {
    pub reply: String,
    /// 截断原因（`length` 表示输出被截断，可重试）；`tool_calls` 表示需执行工具。
    pub finish_reason: Option<String>,
    #[serde(default)]
    pub tool_calls: Vec<AssistantToolCall>,
}

impl ChatResponse {
    pub fn has_tool_calls(&self) -> bool {
        !self.tool_calls.is_empty()
            || self
                .finish_reason
                .as_deref()
                .is_some_and(|r| r == "tool_calls")
    }
}

/// Provider 连接配置（从业务设置中提取）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderSettings {
    /// 规范化后的 provider 类型：openai_compatible / anthropic / gemini / dashscope_app。
    pub provider_type: String,
    pub api_key: String,
    pub base_url: String,
    pub model: String,
}

/// LLM provider 统一接口。
#[async_trait]
pub trait LlmProvider: Send + Sync {
    /// provider 类型标识（openai_compatible / anthropic / gemini / dashscope_app）。
    fn kind(&self) -> &'static str;

    /// 是否支持 OpenAI-style tools / tool_calls（tool loop 前置条件）。
    fn supports_tools(&self) -> bool {
        false
    }

    async fn complete(&self, request: &ChatRequest) -> Result<ChatResponse, LlmError>;
}

/// 按设置构造 provider（策略模式：类型 → 实现）。
pub fn provider_from_settings(
    settings: &ProviderSettings,
) -> Result<Box<dyn LlmProvider>, LlmError> {
    match settings.provider_type.as_str() {
        "anthropic" => Ok(Box::new(anthropic::AnthropicProvider::new(
            settings.clone(),
        ))),
        "gemini" => Ok(Box::new(gemini::GeminiProvider::new(settings.clone()))),
        "dashscope_app" => Ok(Box::new(dashscope::DashScopeAppProvider::new(
            settings.clone(),
        ))),
        // openai_compatible（含 dashscope 兼容模式 / ollama / deepseek 等）。
        _ => Ok(Box::new(openai::OpenAiCompatibleProvider::new(
            settings.clone(),
        ))),
    }
}

/// 规范化 provider 类型字符串（兼容旧配置无 provider 字段的场景）。
pub fn normalize_provider_type(provider_type: &str, base_url: &str, model: &str) -> String {
    let provider = provider_type.trim().to_lowercase().replace('-', "_");
    let provider = match provider.as_str() {
        "openai"
        | "openai_compatible"
        | "openai兼容"
        | "dashscope_compatible"
        | "qwen"
        | "dashscope"
        | "deepseek"
        | "doubao" => "openai_compatible",
        "anthropic" | "claude" => "anthropic",
        "gemini" | "google_gemini" => "gemini",
        "dashscope_app" | "dashscope应用" => "dashscope_app",
        other => other,
    };
    if matches!(
        provider,
        "openai_compatible" | "anthropic" | "gemini" | "dashscope_app"
    ) {
        return provider.to_string();
    }

    let base = base_url.trim().to_lowercase();
    let model = model.trim().to_lowercase();
    if base.contains("generativelanguage.googleapis.com") {
        return "gemini".to_string();
    }
    if base.contains("api.anthropic.com") {
        return "anthropic".to_string();
    }
    if base.contains("/apps/") {
        return "dashscope_app".to_string();
    }
    if model.contains("gemini") {
        return "gemini".to_string();
    }
    if model.contains("claude") {
        return "anthropic".to_string();
    }
    "openai_compatible".to_string()
}

/// 去除首尾空白并清理换行（配置字段清洗）。
pub fn clean_text(value: &str) -> String {
    value.replace(['\r', '\n'], "").trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_provider_types() {
        assert_eq!(
            normalize_provider_type("openai", "", ""),
            "openai_compatible"
        );
        assert_eq!(
            normalize_provider_type("doubao", "", ""),
            "openai_compatible"
        );
        assert_eq!(
            normalize_provider_type("deepseek", "", ""),
            "openai_compatible"
        );
        assert_eq!(normalize_provider_type("claude", "", ""), "anthropic");
        assert_eq!(
            normalize_provider_type("", "https://generativelanguage.googleapis.com", ""),
            "gemini"
        );
        assert_eq!(
            normalize_provider_type("", "https://dashscope.aliyuncs.com/api/v1/apps/xx", ""),
            "dashscope_app"
        );
        assert_eq!(
            normalize_provider_type("", "", "deepseek-chat"),
            "openai_compatible"
        );
    }

    #[test]
    fn builds_provider_by_type() {
        let settings = ProviderSettings {
            provider_type: "openai_compatible".to_string(),
            api_key: String::from("k"),
            base_url: "https://api.deepseek.com/v1".to_string(),
            model: "deepseek-chat".to_string(),
        };
        let provider = provider_from_settings(&settings).expect("provider");
        assert_eq!(provider.kind(), "openai_compatible");
        assert!(provider.supports_tools());
    }
}
