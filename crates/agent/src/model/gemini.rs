//! Google Gemini provider — reqwest 薄封装。

use super::{ChatRequest, ChatResponse, LlmError, LlmProvider, ProviderSettings};
use async_trait::async_trait;
use serde_json::json;

const DEFAULT_BASE_URL: &str = "https://generativelanguage.googleapis.com";

/// Gemini provider。
pub struct GeminiProvider {
    settings: ProviderSettings,
}

impl GeminiProvider {
    pub fn new(settings: ProviderSettings) -> Self {
        Self { settings }
    }

    fn endpoint(&self, model: &str) -> String {
        let base = self.settings.base_url.trim().trim_end_matches('/');
        let base = if base.is_empty() {
            DEFAULT_BASE_URL
        } else {
            base
        };
        format!("{base}/v1beta/models/{model}:generateContent")
    }
}

#[async_trait]
impl LlmProvider for GeminiProvider {
    fn kind(&self) -> &'static str {
        "gemini"
    }

    async fn complete(&self, request: &ChatRequest) -> Result<ChatResponse, LlmError> {
        // Gemini 协议：system 走 systemInstruction；user/assistant 平铺为 contents。
        let system = request
            .messages
            .iter()
            .filter(|msg| msg.role == "system")
            .map(|msg| msg.content.clone())
            .collect::<Vec<_>>()
            .join("\n");
        let contents: Vec<_> = request
            .messages
            .iter()
            .filter(|msg| msg.role != "system")
            .map(|msg| {
                json!({
                    "role": if msg.role == "assistant" { "model" } else { "user" },
                    "parts": [{"text": msg.content}]
                })
            })
            .collect();

        let mut payload = json!({
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            }
        });
        if !system.is_empty() {
            payload["systemInstruction"] = json!({ "parts": [{ "text": system }] });
        }

        let client = reqwest::Client::new();
        let response = client
            .post(self.endpoint(&request.model))
            .query(&[("key", &self.settings.api_key)])
            .json(&payload)
            .send()
            .await
            .map_err(|error| LlmError::Transport(format!("gemini: {error}")))?;
        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|error| LlmError::Transport(format!("gemini parse: {error}")))?;

        let reply = body
            .pointer("/candidates/0/content/parts/0/text")
            .and_then(serde_json::Value::as_str)
            .map(|text| text.trim().to_string())
            .filter(|text| !text.is_empty())
            .ok_or(LlmError::EmptyResponse)?;

        let finish_reason = body
            .pointer("/candidates/0/finishReason")
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
    fn endpoint_uses_model_and_key() {
        let provider = GeminiProvider::new(ProviderSettings {
            provider_type: "gemini".into(),
            api_key: String::from("k"),
            base_url: "".into(),
            model: "gemini-1.5-pro".into(),
        });
        assert_eq!(
            provider.endpoint("gemini-1.5-pro"),
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
        );
    }
}
