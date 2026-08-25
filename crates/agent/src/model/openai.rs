//! OpenAI 兼容 provider — reqwest 直连 `POST /chat/completions`。
//!
//! 覆盖 OpenAI / DeepSeek / 豆包 Ark / 阿里云百炼兼容模式 / Ollama 等所有
//! `POST /chat/completions` 兼容服务。模型基址按兼容协议标准化。
//!
//! 推理模型（DeepSeek R1 / 豆包 Seed 等）默认思考会把 token 预算耗尽，
//! 导致 `content` 为空；调用方显式要求关闭思考时下发 `thinking` 字段。
//!
//! 支持 OpenAI-style `tools` / `tool_calls`（供 [`crate::tool_loop`] 使用）。

use super::{
    AssistantToolCall, ChatMessage, ChatRequest, ChatResponse, LlmError, LlmProvider,
    ProviderSettings, ToolSpec,
};
use async_trait::async_trait;
use serde_json::{json, Value};

/// 标准 OpenAI 兼容端点路径。
const DEFAULT_CHAT_PATH: &str = "/chat/completions";

/// 把基址规范化为 `api_base`（不含 `/chat/completions`，请求时自行拼接）。
fn normalize_base_url(base_url: &str) -> String {
    let base = base_url.trim().trim_end_matches('/');
    if base.is_empty() {
        return "https://api.openai.com/v1".to_string();
    }
    // 去掉用户已填的 `/chat/completions` 结尾。
    let base = base.strip_suffix(DEFAULT_CHAT_PATH).unwrap_or(base);
    // 已含 /v1、/v2、/v3 则直接用。
    if base.ends_with("/v1") || base.ends_with("/v2") || base.ends_with("/v3") {
        return base.to_string();
    }
    format!("{base}/v1")
}

/// OpenAI 兼容 provider。
pub struct OpenAiCompatibleProvider {
    settings: ProviderSettings,
}

impl OpenAiCompatibleProvider {
    pub fn new(settings: ProviderSettings) -> Self {
        Self { settings }
    }
}

fn message_to_json(msg: &ChatMessage) -> Value {
    let mut obj = json!({ "role": msg.role });
    if let Some(tool_call_id) = &msg.tool_call_id {
        obj["tool_call_id"] = json!(tool_call_id);
    }
    if let Some(tool_calls) = &msg.tool_calls {
        let calls: Vec<Value> = tool_calls
            .iter()
            .map(|call| {
                json!({
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                })
            })
            .collect();
        obj["tool_calls"] = Value::Array(calls);
        if msg.content.is_empty() {
            obj["content"] = Value::Null;
        } else {
            obj["content"] = json!(msg.content);
        }
    } else {
        obj["content"] = json!(msg.content);
    }
    obj
}

fn tools_to_json(tools: &[ToolSpec]) -> Value {
    Value::Array(
        tools
            .iter()
            .map(|tool| {
                json!({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                })
            })
            .collect(),
    )
}

/// 构建 `/chat/completions` 请求体。
fn build_payload(request: &ChatRequest, is_openai_official: bool) -> Value {
    let messages: Vec<Value> = request.messages.iter().map(message_to_json).collect();
    let mut payload = json!({
        "model": request.model,
        "messages": messages,
        "temperature": request.temperature,
    });
    if is_openai_official {
        payload["max_completion_tokens"] = json!(request.max_tokens);
    } else {
        payload["max_tokens"] = json!(request.max_tokens);
    }
    if request.disable_thinking {
        payload["thinking"] = json!({ "type": "disabled" });
    }
    if let Some(tools) = &request.tools {
        if !tools.is_empty() {
            payload["tools"] = tools_to_json(tools);
            match request.tool_choice.as_deref() {
                None | Some("auto") => payload["tool_choice"] = json!("auto"),
                Some("none") => payload["tool_choice"] = json!("none"),
                Some(name) => {
                    payload["tool_choice"] = json!({
                        "type": "function",
                        "function": { "name": name }
                    });
                }
            }
        }
    }
    payload
}

fn parse_tool_calls(message: &Value) -> Vec<AssistantToolCall> {
    let Some(Value::Array(calls)) = message.get("tool_calls") else {
        return Vec::new();
    };
    calls
        .iter()
        .filter_map(|call| {
            let id = call
                .get("id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let function = call.get("function")?;
            let name = function
                .get("name")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if name.is_empty() {
                return None;
            }
            let arguments = match function.get("arguments") {
                Some(Value::String(s)) => s.clone(),
                Some(other) => other.to_string(),
                None => "{}".to_string(),
            };
            let id = if id.is_empty() {
                format!("call_{name}")
            } else {
                id
            };
            Some(AssistantToolCall {
                id,
                name,
                arguments,
            })
        })
        .collect()
}

#[async_trait]
impl LlmProvider for OpenAiCompatibleProvider {
    fn kind(&self) -> &'static str {
        "openai_compatible"
    }

    fn supports_tools(&self) -> bool {
        true
    }

    async fn complete(&self, request: &ChatRequest) -> Result<ChatResponse, LlmError> {
        let base_url = normalize_base_url(&self.settings.base_url);
        let is_openai_official = base_url.contains("api.openai.com");
        let url = format!("{base_url}{DEFAULT_CHAT_PATH}");
        let payload = build_payload(request, is_openai_official);

        let response = reqwest::Client::new()
            .post(&url)
            .bearer_auth(&self.settings.api_key)
            .json(&payload)
            .send()
            .await
            .map_err(|error| LlmError::Transport(format!("openai compatible: {error}")))?;
        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            return Err(LlmError::Provider(format!(
                "openai compatible: HTTP {status}: {text}"
            )));
        }
        let body: Value = response
            .json()
            .await
            .map_err(|error| LlmError::Transport(format!("openai compatible parse: {error}")))?;
        let choice = body
            .get("choices")
            .and_then(Value::as_array)
            .and_then(|choices| choices.first())
            .ok_or(LlmError::EmptyResponse)?;
        let message = choice.get("message").ok_or(LlmError::EmptyResponse)?;
        let tool_calls = parse_tool_calls(message);
        let reply = message
            .get("content")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|content| !content.is_empty())
            .map(str::to_string)
            .unwrap_or_default();
        let finish_reason = choice
            .get("finish_reason")
            .and_then(Value::as_str)
            .map(str::to_string);

        if reply.is_empty() && tool_calls.is_empty() {
            let thinking = message
                .get("reasoning_content")
                .and_then(Value::as_str)
                .is_some_and(|content| !content.is_empty());
            return Err(if thinking {
                LlmError::Provider(
                    "模型处于思考模式且未输出正文（content 为空），请关闭思考或换用非推理模型"
                        .to_string(),
                )
            } else {
                LlmError::EmptyResponse
            });
        }

        Ok(ChatResponse {
            reply,
            finish_reason,
            tool_calls,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::ChatMessage;

    fn request(disable_thinking: bool) -> ChatRequest {
        ChatRequest {
            model: "doubao-seed-2-0-mini".to_string(),
            messages: vec![ChatMessage::user("hi")],
            max_tokens: 512,
            temperature: 0.2,
            disable_thinking,
            ..Default::default()
        }
    }

    #[test]
    fn normalizes_common_base_urls() {
        assert_eq!(
            normalize_base_url("https://api.deepseek.com"),
            "https://api.deepseek.com/v1"
        );
        assert_eq!(
            normalize_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        );
        assert_eq!(
            normalize_base_url("https://ark.cn-beijing.volces.com/api/v3"),
            "https://ark.cn-beijing.volces.com/api/v3"
        );
        assert_eq!(normalize_base_url(""), "https://api.openai.com/v1");
    }

    #[test]
    fn strips_chat_path_from_full_endpoint() {
        assert_eq!(
            normalize_base_url("https://ark.cn-beijing.volces.com/api/v3/chat/completions"),
            "https://ark.cn-beijing.volces.com/api/v3"
        );
        assert_eq!(
            normalize_base_url("http://localhost:11434/v1/chat/completions"),
            "http://localhost:11434/v1"
        );
    }

    #[test]
    fn disables_thinking_when_requested() {
        let payload = build_payload(&request(true), false);
        assert_eq!(payload["max_tokens"], 512);
        assert_eq!(payload["thinking"]["type"], "disabled");
    }

    #[test]
    fn official_openai_uses_max_completion_tokens() {
        let payload = build_payload(&request(false), true);
        assert!(payload.get("max_completion_tokens").is_some());
        assert!(payload.get("max_tokens").is_none());
        assert!(payload.get("thinking").is_none());
    }

    #[test]
    fn serializes_tools_and_tool_messages() {
        let mut req = request(false);
        req.tools = Some(vec![ToolSpec {
            name: "web_search".into(),
            description: "search".into(),
            parameters: json!({"type":"object","properties":{"query":{"type":"string"}}}),
        }]);
        req.tool_choice = Some("auto".into());
        req.messages.push(ChatMessage::assistant_tools(
            "",
            vec![AssistantToolCall {
                id: "c1".into(),
                name: "web_search".into(),
                arguments: r#"{"query":"iphone"}"#.into(),
            }],
        ));
        req.messages
            .push(ChatMessage::tool("c1", "Sources:\n- [a](https://ex.com)"));
        let payload = build_payload(&req, false);
        assert_eq!(payload["tools"][0]["function"]["name"], "web_search");
        assert_eq!(payload["tool_choice"], "auto");
        assert!(payload["messages"][1]["content"].is_null());
        assert_eq!(payload["messages"][1]["tool_calls"][0]["id"], "c1");
        assert_eq!(payload["messages"][2]["role"], "tool");
        assert_eq!(payload["messages"][2]["tool_call_id"], "c1");
    }

    #[test]
    fn parses_tool_calls_from_message() {
        let message = json!({
            "role": "assistant",
            "content": null,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": { "name": "web_search", "arguments": "{\"query\":\"x\"}" }
            }]
        });
        let calls = parse_tool_calls(&message);
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].name, "web_search");
        assert_eq!(calls[0].arguments, r#"{"query":"x"}"#);
    }
}
