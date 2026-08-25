//! DuckDuckGo Instant Answer provider — 无 API key，经 [`NetworkSandbox`] 出站。

use std::sync::Arc;

use async_trait::async_trait;
use serde_json::Value;

use crate::sandbox::{NetworkPolicy, NetworkSandbox};

use super::{WebError, WebSearchProvider, WebSearchRequest, WebSearchResult, WebSearchSource};

pub const PROVIDER_ID: &str = "duckduckgo";

const ALLOWED_HOST: &str = "api.duckduckgo.com";

pub struct DuckDuckGoSearchProvider {
    sandbox: Arc<NetworkSandbox>,
}

impl Default for DuckDuckGoSearchProvider {
    fn default() -> Self {
        Self::new(Arc::new(NetworkSandbox::new(NetworkPolicy::with_hosts([
            ALLOWED_HOST,
        ]))))
    }
}

impl DuckDuckGoSearchProvider {
    pub fn new(sandbox: Arc<NetworkSandbox>) -> Self {
        Self { sandbox }
    }
}

#[async_trait]
impl WebSearchProvider for DuckDuckGoSearchProvider {
    fn id(&self) -> &str {
        PROVIDER_ID
    }

    fn available(&self) -> bool {
        true
    }

    async fn search(&self, request: &WebSearchRequest) -> Result<WebSearchResult, WebError> {
        let query = request.query.trim();
        if query.is_empty() {
            return Err(WebError::Provider("query must be non-empty".into()));
        }

        let mut url = url::Url::parse("https://api.duckduckgo.com/")
            .map_err(|e| WebError::Provider(e.to_string()))?;
        {
            let mut qp = url.query_pairs_mut();
            qp.append_pair("q", query);
            qp.append_pair("format", "json");
            qp.append_pair("no_redirect", "1");
            qp.append_pair("no_html", "1");
            qp.append_pair("skip_disambig", "1");
        }

        let body = self
            .sandbox
            .get_text(url.as_str())
            .await
            .map_err(|e| WebError::Provider(e.to_string()))?;

        let json: Value =
            serde_json::from_str(&body).map_err(|e| WebError::Provider(format!("json: {e}")))?;

        let mut sources = Vec::new();
        let abstract_text = json
            .get("AbstractText")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        let abstract_url = json
            .get("AbstractURL")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty());
        let heading = json
            .get("Heading")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty());

        if let (Some(url), Some(title)) = (abstract_url, heading.or(abstract_text.as_deref())) {
            sources.push(WebSearchSource {
                url: url.to_string(),
                title: Some(title.to_string()),
                snippet: abstract_text.clone(),
                published_at: None,
            });
        }

        push_related(&mut sources, json.get("RelatedTopics"));
        push_related(&mut sources, json.get("Results"));

        Ok(WebSearchResult {
            content: abstract_text,
            sources,
            truncated: false,
        })
    }
}

fn push_related(sources: &mut Vec<WebSearchSource>, node: Option<&Value>) {
    let Some(Value::Array(items)) = node else {
        return;
    };
    for item in items {
        if let Some(topics) = item.get("Topics").and_then(Value::as_array) {
            for nested in topics {
                push_topic(sources, nested);
            }
            continue;
        }
        push_topic(sources, item);
    }
}

fn push_topic(sources: &mut Vec<WebSearchSource>, item: &Value) {
    let url = item
        .get("FirstURL")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let text = item
        .get("Text")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let Some(url) = url else {
        return;
    };
    let (title, snippet) = match text {
        Some(t) => {
            let title = t.split(" - ").next().unwrap_or(t).to_string();
            (Some(title), Some(t.to_string()))
        }
        None => (None, None),
    };
    sources.push(WebSearchSource {
        url: url.to_string(),
        title,
        snippet,
        published_at: None,
    });
}
