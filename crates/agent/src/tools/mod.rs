//! 工具注册与执行流水线（参考 deepseek-harness tools pre → execute → post）。
//!
//! MVP：同步注册表 + timeout 环绕；不实现 approval waterfall / Cordis 事件。

pub mod web_search;

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use serde_json::Value;
use thiserror::Error;
use tokio::time::timeout;

use crate::web::WebRuntime;

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum ToolError {
    #[error("tool `{0}` not found")]
    NotFound(String),
    #[error("tool `{0}` denied: {1}")]
    Denied(String, String),
    #[error("tool `{0}` timed out")]
    Timeout(String),
    #[error("tool `{0}` failed: {1}")]
    Failed(String, String),
}

#[derive(Debug, Clone)]
pub struct ToolCall {
    pub name: String,
    pub arguments: Value,
}

#[derive(Debug, Clone)]
pub struct ToolResult {
    pub name: String,
    pub content: String,
    pub is_error: bool,
    pub meta: Option<Value>,
}

#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    /// JSON Schema 风格参数说明（给模型看的文本即可）。
    fn parameters_hint(&self) -> &str;
    async fn execute(&self, arguments: &Value) -> Result<ToolResult, ToolError>;
}

/// 简易 ToolRuntime：pre（存在性）→ execute（timeout）→ post（错误归一）。
pub struct ToolRuntime {
    tools: HashMap<String, Arc<dyn Tool>>,
    default_timeout: Duration,
}

impl Default for ToolRuntime {
    fn default() -> Self {
        Self::new(Duration::from_secs(20))
    }
}

impl ToolRuntime {
    pub fn new(default_timeout: Duration) -> Self {
        Self {
            tools: HashMap::new(),
            default_timeout,
        }
    }

    pub fn register(&mut self, tool: Arc<dyn Tool>) {
        self.tools.insert(tool.name().to_string(), tool);
    }

    pub fn list_descriptions(&self) -> Vec<(String, String, String)> {
        self.tools
            .values()
            .map(|t| {
                (
                    t.name().to_string(),
                    t.description().to_string(),
                    t.parameters_hint().to_string(),
                )
            })
            .collect()
    }

    pub async fn invoke(&self, call: &ToolCall) -> ToolResult {
        let Some(tool) = self.tools.get(&call.name) else {
            return ToolResult {
                name: call.name.clone(),
                content: format!("tool `{}` not found", call.name),
                is_error: true,
                meta: None,
            };
        };

        let name = tool.name().to_string();
        let fut = tool.execute(&call.arguments);
        match timeout(self.default_timeout, fut).await {
            Ok(Ok(mut result)) => {
                result.name = name;
                result
            }
            Ok(Err(error)) => ToolResult {
                name,
                content: error.to_string(),
                is_error: true,
                meta: None,
            },
            Err(_) => ToolResult {
                name: name.clone(),
                content: ToolError::Timeout(name).to_string(),
                is_error: true,
                meta: None,
            },
        }
    }
}

/// 默认工具包：仅 `web_search`。
pub fn default_tool_runtime(web: Arc<WebRuntime>) -> ToolRuntime {
    let mut runtime = ToolRuntime::default();
    runtime.register(Arc::new(web_search::WebSearchTool::new(web)));
    runtime
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::web::{WebSearchProvider, WebSearchRequest, WebSearchResult, WebSearchSource};

    struct StubSearch;

    #[async_trait]
    impl WebSearchProvider for StubSearch {
        fn id(&self) -> &str {
            "stub"
        }
        fn available(&self) -> bool {
            true
        }
        async fn search(
            &self,
            request: &WebSearchRequest,
        ) -> Result<WebSearchResult, crate::web::WebError> {
            Ok(WebSearchResult {
                content: Some(format!("answer for {}", request.query)),
                sources: vec![WebSearchSource {
                    url: "https://example.com/a".into(),
                    title: Some("Example".into()),
                    snippet: Some("snippet".into()),
                    published_at: None,
                }],
                truncated: false,
            })
        }
    }

    #[tokio::test]
    async fn web_search_tool_formats() {
        let mut web = WebRuntime::new(Some("stub".into()));
        web.register_search_provider(Arc::new(StubSearch)).unwrap();
        let tools = default_tool_runtime(Arc::new(web));
        let result = tools
            .invoke(&ToolCall {
                name: "web_search".into(),
                arguments: serde_json::json!({ "query": "iphone 行情" }),
            })
            .await;
        assert!(!result.is_error);
        assert!(result.content.contains("Sources:"));
        assert!(result.content.contains("example.com"));
    }

    #[tokio::test]
    async fn unknown_tool_is_error() {
        let tools = ToolRuntime::default();
        let result = tools
            .invoke(&ToolCall {
                name: "nope".into(),
                arguments: serde_json::json!({}),
            })
            .await;
        assert!(result.is_error);
    }
}
