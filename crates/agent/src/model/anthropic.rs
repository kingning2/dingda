//! Anthropic Claude provider — reqwest 薄封装（官方协议无统一第三方库）。

use super::{ChatRequest, ChatResponse, LlmError, LlmProvider, ProviderSettings};
use async_trait::async_trait;
use serde_json::json;

const DEFAULT_BASE_URL: &str = "https://api.anthropic.com";
const API_VERSION: &str = "2023-06-01";

/// Anthropic provider。
pub struct AnthropicProvider {
    settings: ProviderSettings,
}

impl AnthropicProvider {
    pub fn new(settings: ProviderSettings) -> Self {
        Self { settings }
    }

    fn endpoint(&self) -> String {
        let base = self.settings.base_url.trim().trim_end_matches('/');
        let base = if base.is_empty() {
            DEFAULT_BASE_URL
        } else {
            base
        };
        format!("{base}/v1/messages")
    }
}

#[async_trait]
impl LlmProvider for AnthropicProvider {
    fn kind(&self) -> &'static str {
        "anthropic"
    }

    async fn complete(&self, request: &ChatRequest) -> Result<ChatResponse, LlmError> {
        // Anthropic 协议：system 单独字段，其余 role 仅 user/assistant。
        let system = request
            .messages
            .iter()
            .filter(|msg| msg.role == "system")
            .map(|msg| msg.content.clone())
            .collect::<Vec<_>>()
            .join("\n");
        let messages: Vec<_> = request
            .messages
            .iter()
            .filter(|msg| msg.role != "system")
            .map(|msg| json!({ "role": msg.role, "content": msg.content }))
            .collect();

        let mut payload = json!({
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        });
        if !system.is_empty() {
            payload["system"] = json!(system);
        }

        let client = reqwest::Client::new();
        let response = client
            .post(self.endpoint())
            .header("x-api-key", &self.settings.api_key)
            .header("anthropic-version", API_VERSION)
            .json(&payload)
            .send()
            .await
            .map_err(|error| LlmError::Transport(format!("anthropic: {error}")))?;
        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|error| LlmError::Transport(format!("anthropic parse: {error}")))?;

        let reply = body
            .get("content")
            .and_then(serde_json::Value::as_array)
            .and_then(|parts| {
                parts
                    .iter()
                    .find(|part| {
                        part.get("type").and_then(serde_json::Value::as_str) == Some("text")
                    })
                    .and_then(|part| part.get("text").and_then(serde_json::Value::as_str))
            })
            .map(|text| text.trim().to_string())
            .filter(|text| !text.is_empty())
            .ok_or(LlmError::EmptyResponse)?;

        let finish_reason = body
            .get("stop_reason")
            .and_then(serde_json::Value::as_str)
            .map(|s| s.to_string());

        Ok(ChatResponse {
            reply,
            finish_reason,
            tool_calls: Vec::new(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn endpoint_defaults_to_official() {
        let provider = AnthropicProvider::new(ProviderSettings {
            provider_type: "anthropic".into(),
            api_key: String::from("k"),
            base_url: "".into(),
            model: "claude-3-5-sonnet".into(),
        });
        assert_eq!(provider.endpoint(), "https://api.anthropic.com/v1/messages");
    }

    #[test]
    fn endpoint_respects_custom_base() {
        let provider = AnthropicProvider::new(ProviderSettings {
            provider_type: "anthropic".into(),
            api_key: String::from("k"),
            base_url: "https://proxy.example.com".into(),
            model: "claude".into(),
        });
        assert_eq!(provider.endpoint(), "https://proxy.example.com/v1/messages");
    }
}
