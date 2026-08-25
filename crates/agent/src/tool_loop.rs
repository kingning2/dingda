//! OpenAI-compatible tool loop（参考 deepseek-harness agent-loop 精神）。
//!
//! 流程：`complete(tools)` → 若有 `tool_calls` → `ToolRuntime` 执行 → 追加
//! assistant/tool 消息 → 再 complete，直至无 tool_calls 或达 `max_rounds`。

use crate::model::{AssistantToolCall, ChatMessage, ChatRequest, LlmError, LlmProvider, ToolSpec};
use crate::tools::{ToolCall, ToolResult, ToolRuntime};
use serde_json::Value;

/// 单次工具执行痕迹（供转录 / 调试）。
#[derive(Debug, Clone)]
pub struct ToolTraceEntry {
    pub round: usize,
    pub call: AssistantToolCall,
    pub result: ToolResult,
}

/// tool loop 最终结果。
#[derive(Debug, Clone)]
pub struct ToolLoopOutcome {
    pub reply: String,
    pub finish_reason: Option<String>,
    pub messages: Vec<ChatMessage>,
    pub tool_trace: Vec<ToolTraceEntry>,
    pub rounds: usize,
}

/// tool loop 配置。
#[derive(Debug, Clone)]
pub struct ToolLoopConfig {
    pub max_rounds: usize,
    pub tool_choice: Option<String>,
}

impl Default for ToolLoopConfig {
    fn default() -> Self {
        Self {
            max_rounds: 4,
            tool_choice: Some("auto".into()),
        }
    }
}

/// 运行 tool loop。
///
/// - provider 若不支持 tools，退化为单次 `complete`（忽略 tools）。
/// - 每轮并行语义：顺序执行本轮全部 tool_calls（简单可靠）。
pub async fn run(
    provider: &dyn LlmProvider,
    tools: &ToolRuntime,
    mut request: ChatRequest,
    config: ToolLoopConfig,
) -> Result<ToolLoopOutcome, LlmError> {
    let max_rounds = config.max_rounds.max(1);
    let specs = tools.openai_tool_specs();

    if provider.supports_tools() && !specs.is_empty() {
        request.tools = Some(specs);
        request.tool_choice = config.tool_choice.clone();
    } else {
        request.tools = None;
        request.tool_choice = None;
    }

    let mut tool_trace = Vec::new();
    let mut rounds = 0usize;

    loop {
        rounds += 1;
        let response = provider.complete(&request).await?;

        if !response.has_tool_calls() || response.tool_calls.is_empty() {
            return Ok(ToolLoopOutcome {
                reply: response.reply,
                finish_reason: response.finish_reason,
                messages: request.messages,
                tool_trace,
                rounds,
            });
        }

        if rounds >= max_rounds {
            return Err(LlmError::ToolLoopExhausted(max_rounds));
        }

        if !provider.supports_tools() {
            // 不应走到这里；防御。
            return Ok(ToolLoopOutcome {
                reply: response.reply,
                finish_reason: response.finish_reason,
                messages: request.messages,
                tool_trace,
                rounds,
            });
        }

        request.messages.push(ChatMessage::assistant_tools(
            response.reply.clone(),
            response.tool_calls.clone(),
        ));

        for call in &response.tool_calls {
            let result = tools.invoke_assistant_call(call).await;
            tool_trace.push(ToolTraceEntry {
                round: rounds,
                call: call.clone(),
                result: result.clone(),
            });
            request
                .messages
                .push(ChatMessage::tool(&call.id, &result.content));
        }
    }
}

/// 便捷：无额外配置跑默认 tool loop。
pub async fn run_default(
    provider: &dyn LlmProvider,
    tools: &ToolRuntime,
    request: ChatRequest,
) -> Result<ToolLoopOutcome, LlmError> {
    run(provider, tools, request, ToolLoopConfig::default()).await
}

/// 从 [`ToolRuntime`] 拼装的单次请求（已填 tools）。
pub fn request_with_tools(
    model: impl Into<String>,
    messages: Vec<ChatMessage>,
    tools: &[ToolSpec],
    max_tokens: u32,
    temperature: f32,
) -> ChatRequest {
    ChatRequest {
        model: model.into(),
        messages,
        max_tokens,
        temperature,
        disable_thinking: true,
        tools: if tools.is_empty() {
            None
        } else {
            Some(tools.to_vec())
        },
        tool_choice: Some("auto".into()),
    }
}

impl ToolRuntime {
    /// OpenAI `tools` 数组规格。
    pub fn openai_tool_specs(&self) -> Vec<ToolSpec> {
        self.list_descriptions()
            .into_iter()
            .map(|(name, description, parameters_hint)| {
                let parameters =
                    serde_json::from_str::<Value>(&parameters_hint).unwrap_or_else(|_| {
                        serde_json::json!({
                            "type": "object",
                            "properties": {},
                        })
                    });
                ToolSpec {
                    name,
                    description,
                    parameters,
                }
            })
            .collect()
    }

    /// 执行模型发出的 [`AssistantToolCall`]。
    pub async fn invoke_assistant_call(&self, call: &AssistantToolCall) -> ToolResult {
        let arguments = parse_tool_arguments(&call.arguments);
        self.invoke(&ToolCall {
            name: call.name.clone(),
            arguments,
        })
        .await
    }
}

fn parse_tool_arguments(raw: &str) -> Value {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Value::Object(Default::default());
    }
    serde_json::from_str(trimmed).unwrap_or_else(|_| serde_json::json!({ "raw": trimmed }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{
        AssistantToolCall, ChatMessage, ChatRequest, ChatResponse, LlmError, LlmProvider,
    };
    use crate::tools::{Tool, ToolError};
    use crate::web::{
        WebError, WebRuntime, WebSearchProvider, WebSearchRequest, WebSearchResult, WebSearchSource,
    };
    use async_trait::async_trait;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    struct ScriptedProvider {
        step: AtomicUsize,
    }

    #[async_trait]
    impl LlmProvider for ScriptedProvider {
        fn kind(&self) -> &'static str {
            "openai_compatible"
        }
        fn supports_tools(&self) -> bool {
            true
        }
        async fn complete(&self, request: &ChatRequest) -> Result<ChatResponse, LlmError> {
            let n = self.step.fetch_add(1, Ordering::SeqCst);
            if n == 0 {
                assert!(request.tools.as_ref().is_some_and(|t| !t.is_empty()));
                Ok(ChatResponse {
                    reply: String::new(),
                    finish_reason: Some("tool_calls".into()),
                    tool_calls: vec![AssistantToolCall {
                        id: "c1".into(),
                        name: "web_search".into(),
                        arguments: r#"{"query":"iphone"}"#.into(),
                    }],
                })
            } else {
                assert!(request
                    .messages
                    .iter()
                    .any(|m| m.role == "tool" && m.tool_call_id.as_deref() == Some("c1")));
                Ok(ChatResponse {
                    reply: r#"{"recommended":true,"reason":"ok"}"#.into(),
                    finish_reason: Some("stop".into()),
                    tool_calls: vec![],
                })
            }
        }
    }

    struct StubSearch;

    #[async_trait]
    impl WebSearchProvider for StubSearch {
        fn id(&self) -> &str {
            "stub"
        }
        fn available(&self) -> bool {
            true
        }
        async fn search(&self, request: &WebSearchRequest) -> Result<WebSearchResult, WebError> {
            Ok(WebSearchResult {
                content: Some(format!("hit {}", request.query)),
                sources: vec![WebSearchSource {
                    url: "https://example.com".into(),
                    title: Some("ex".into()),
                    snippet: None,
                    published_at: None,
                }],
                truncated: false,
            })
        }
    }

    #[tokio::test]
    async fn loops_until_final_text() {
        let mut web = WebRuntime::new(Some("stub".into()));
        web.register_search_provider(Arc::new(StubSearch)).unwrap();
        let tools = crate::tools::default_tool_runtime(Arc::new(web));
        let provider = ScriptedProvider {
            step: AtomicUsize::new(0),
        };
        let outcome = run(
            &provider,
            &tools,
            ChatRequest {
                model: "m".into(),
                messages: vec![ChatMessage::user("decide")],
                max_tokens: 256,
                temperature: 0.0,
                disable_thinking: true,
                ..Default::default()
            },
            ToolLoopConfig::default(),
        )
        .await
        .unwrap();
        assert_eq!(outcome.rounds, 2);
        assert_eq!(outcome.tool_trace.len(), 1);
        assert!(outcome.reply.contains("recommended"));
        assert!(!outcome.tool_trace[0].result.is_error);
    }

    struct EchoTool;

    #[async_trait]
    impl Tool for EchoTool {
        fn name(&self) -> &str {
            "echo"
        }
        fn description(&self) -> &str {
            "echo"
        }
        fn parameters_hint(&self) -> &str {
            r#"{"type":"object","properties":{"x":{"type":"string"}},"required":["x"]}"#
        }
        async fn execute(&self, arguments: &Value) -> Result<ToolResult, ToolError> {
            Ok(ToolResult {
                name: "echo".into(),
                content: arguments.to_string(),
                is_error: false,
                meta: None,
            })
        }
    }

    #[tokio::test]
    async fn exhausted_rounds_errors() {
        struct AlwaysTools;
        #[async_trait]
        impl LlmProvider for AlwaysTools {
            fn kind(&self) -> &'static str {
                "openai_compatible"
            }
            fn supports_tools(&self) -> bool {
                true
            }
            async fn complete(&self, _request: &ChatRequest) -> Result<ChatResponse, LlmError> {
                Ok(ChatResponse {
                    reply: String::new(),
                    finish_reason: Some("tool_calls".into()),
                    tool_calls: vec![AssistantToolCall {
                        id: "c".into(),
                        name: "echo".into(),
                        arguments: r#"{"x":"1"}"#.into(),
                    }],
                })
            }
        }
        let mut tools = ToolRuntime::default();
        tools.register(Arc::new(EchoTool));
        let err = run(
            &AlwaysTools,
            &tools,
            ChatRequest {
                model: "m".into(),
                messages: vec![ChatMessage::user("x")],
                max_tokens: 64,
                temperature: 0.0,
                disable_thinking: true,
                ..Default::default()
            },
            ToolLoopConfig {
                max_rounds: 2,
                tool_choice: Some("auto".into()),
            },
        )
        .await
        .unwrap_err();
        assert!(matches!(err, LlmError::ToolLoopExhausted(2)));
    }
}
