//! DashScope App provider — 阿里云百炼应用级接口。
//!
//! 协议：`POST /api/v1/apps/{app_id}/completion`，system 与 user 合并为 prompt。

use super::{ChatRequest, ChatResponse, LlmError, LlmProvider, ProviderSettings};
use async_trait::async_trait;
use serde_json::json;

const DEFAULT_BASE_URL: &str = "https://dashscope.aliyuncs.com/api/v1/apps";

/// DashScope App provider。
pub struct DashScopeAppProvider {
    settings: ProviderSettings,
}

impl DashScopeAppProvider {
    pub fn new(settings: ProviderSettings) -> Self {
        Self { settings }
    }

    /// 从基址或模型名提取 app_id。
    fn app_id(&self) -> Result<String, LlmError> {
        let base = self.settings.base_url.trim();
        if let Some(idx) = base.find("/apps/") {
            let after = &base[idx + "/apps/".len()..];
            let app_id = after.split('/').next().unwrap_or_default().to_string();
            if !app_id.is_empty() {
                return Ok(app_id);
            }
        }
        let model = self.settings.model.trim();
        if !model.is_empty() {
            return Ok(model.to_string());
        }
        Err(LlmError::Provider(
            "dashscope_app: 基址或模型名中未找到 app_id".to_string(),
        ))
    }

    fn endpoint(&self, app_id: &str) -> String {
        format!("{DEFAULT_BASE_URL}/{app_id}/completion")
    }
}

#[async_trait]
impl LlmProvider for DashScopeAppProvider {
    fn kind(&self) -> &'static str {
        "dashscope_app"
    }

    async fn complete(&self, request: &ChatRequest) -> Result<ChatResponse, LlmError> {
        let app_id = self.app_id()?;

        // 协议：system 与 user 拼接为 prompt。
        let system = request
            .messages
            .iter()
            .filter(|msg| msg.role == "system")
            .map(|msg| msg.content.clone())
            .collect::<Vec<_>>()
            .join("\n");
        let user = request
            .messages
            .iter()
            .filter(|msg| msg.role == "user")
            .map(|msg| msg.content.clone())
            .collect::<Vec<_>>()
            .join("\n");
        let prompt = if system.is_empty() {
            user
        } else if user.is_empty() {
            system
        } else {
            format!("{system}\n\n用户问题：{user}\n\n请直接回答用户的问题：")
        };

        let payload = json!({
            "input": { "prompt": prompt },
            "parameters": {
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
            "debug": {},
        });

        let client = reqwest::Client::new();
        let response = client
            .post(self.endpoint(&app_id))
            .bearer_auth(&self.settings.api_key)
            .json(&payload)
            .send()
            .await
            .map_err(|error| LlmError::Transport(format!("dashscope_app: {error}")))?;
        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|error| LlmError::Transport(format!("dashscope_app parse: {error}")))?;

        let reply = body
            .pointer("/output/text")
            .and_then(serde_json::Value::as_str)
            .map(|text| text.trim().to_string())
            .filter(|text| !text.is_empty())
            .ok_or(LlmError::EmptyResponse)?;

        Ok(ChatResponse {
            reply,
            finish_reason: None,
            tool_calls: Vec::new(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_app_id_from_base_url() {
        let provider = DashScopeAppProvider::new(ProviderSettings {
            provider_type: "dashscope_app".into(),
            api_key: String::from("k"),
            base_url: "https://dashscope.aliyuncs.com/api/v1/apps/app-123".into(),
            model: "".into(),
        });
        assert_eq!(provider.app_id().expect("app id"), "app-123");
        assert_eq!(
            provider.endpoint("app-123"),
            "https://dashscope.aliyuncs.com/api/v1/apps/app-123/completion"
        );
    }

    #[test]
    fn falls_back_to_model_as_app_id() {
        let provider = DashScopeAppProvider::new(ProviderSettings {
            provider_type: "dashscope_app".into(),
            api_key: String::from("k"),
            base_url: "".into(),
            model: "app-xyz".into(),
        });
        assert_eq!(provider.app_id().expect("app id"), "app-xyz");
    }
}
