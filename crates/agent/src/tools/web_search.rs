//! 模型侧 `web_search` 工具：只校验参数、调用 `WebRuntime`、格式化结果。
//! 不负责 provider 选择或直连网络（与 harness `dsh-tool-web` 一致）。

use std::sync::Arc;

use async_trait::async_trait;
use serde_json::Value;

use crate::web::{WebRuntime, WebSearchRequest, WebSearchResult, WebSearchSource};

use super::{Tool, ToolError, ToolResult};

/// 默认返回条数上限（与 harness `WEB_SEARCH_MAX_RESULTS = 8` 对齐）。
pub const WEB_SEARCH_MAX_RESULTS: usize = 8;

pub struct WebSearchTool {
    web: Arc<WebRuntime>,
    max_results: usize,
}

impl WebSearchTool {
    pub fn new(web: Arc<WebRuntime>) -> Self {
        Self {
            web,
            max_results: WEB_SEARCH_MAX_RESULTS,
        }
    }

    pub fn with_max_results(mut self, max_results: usize) -> Self {
        self.max_results = max_results.max(1);
        self
    }
}

#[async_trait]
impl Tool for WebSearchTool {
    fn name(&self) -> &str {
        "web_search"
    }

    fn description(&self) -> &str {
        "Search the public web for current information. Prefer concise queries."
    }

    fn parameters_hint(&self) -> &str {
        r#"{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}"#
    }

    async fn execute(&self, arguments: &Value) -> Result<ToolResult, ToolError> {
        let query = arguments
            .get("query")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .ok_or_else(|| {
                ToolError::Failed(
                    "web_search".into(),
                    "query must be a non-empty string".into(),
                )
            })?;

        let result = self
            .web
            .search(&WebSearchRequest {
                query: query.to_string(),
                max_results: Some(self.max_results),
            })
            .await
            .map_err(|e| ToolError::Failed("web_search".into(), e.to_string()))?;

        let meta = search_meta(&result);
        Ok(ToolResult {
            name: "web_search".into(),
            content: format_search_output(&result),
            is_error: false,
            meta: Some(meta),
        })
    }
}

fn source_label(url: &str, title: Option<&str>) -> String {
    if let Some(title) = title.filter(|t| !t.is_empty()) {
        return title.to_string();
    }
    url::Url::parse(url)
        .ok()
        .and_then(|u| u.host_str().map(str::to_string))
        .unwrap_or_else(|| url.to_string())
}

/// 格式化为模型可读文本（与 harness `formatSearchOutput` 对齐）。
pub fn format_search_output(result: &WebSearchResult) -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(content) = result
        .content
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        parts.push(content.to_string());
    }

    if !result.sources.is_empty() {
        let lines: Vec<String> = result
            .sources
            .iter()
            .map(|source| {
                let label = source_label(&source.url, source.title.as_deref());
                let mut meta = Vec::new();
                if let Some(snippet) = source.snippet.as_deref().filter(|s| !s.is_empty()) {
                    meta.push(snippet.to_string());
                }
                if let Some(published) = source.published_at.as_deref().filter(|s| !s.is_empty()) {
                    meta.push(format!("({published})"));
                }
                let suffix = if meta.is_empty() {
                    String::new()
                } else {
                    format!(" — {}", meta.join(" "))
                };
                format!("- [{label}]({}){suffix}", source.url)
            })
            .collect();
        parts.push(format!("Sources:\n{}", lines.join("\n")));
    } else if result.content.as_deref().unwrap_or("").trim().is_empty() {
        parts.push("No results found.".into());
    }

    if result.truncated {
        parts.push(format!(
            "(Showing the first {} sources. Refine the query for more.)",
            result.sources.len()
        ));
    }
    parts.push("Cite the relevant URLs above as markdown links in your answer.".into());
    parts.join("\n\n")
}

fn project_source(source: &WebSearchSource) -> Value {
    let mut obj = serde_json::json!({ "url": source.url });
    if let Some(title) = &source.title {
        obj["title"] = Value::String(title.clone());
    }
    if let Some(snippet) = &source.snippet {
        obj["snippet"] = Value::String(snippet.clone());
    }
    if let Some(published_at) = &source.published_at {
        obj["publishedAt"] = Value::String(published_at.clone());
    }
    obj
}

fn search_meta(result: &WebSearchResult) -> Value {
    let mut meta = serde_json::json!({
        "sources": result.sources.iter().map(project_source).collect::<Vec<_>>(),
        "truncated": result.truncated,
    });
    if let Some(answer) = &result.content {
        meta["answer"] = Value::String(answer.clone());
    }
    meta
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_empty() {
        let text = format_search_output(&WebSearchResult {
            content: None,
            sources: vec![],
            truncated: false,
        });
        assert!(text.contains("No results found."));
    }
}
