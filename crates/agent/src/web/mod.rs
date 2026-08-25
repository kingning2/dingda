//! Web 能力 seam（参考 deepseek-harness `ctx.web`）。
//!
//! - 定义：[`WebSearchProvider`] / [`WebSearchRequest`] / [`WebSearchResult`]
//! - 实现：[`duckduckgo`] 等 provider
//! - 消费：[`crate::tools::web_search`] 工具只做参数校验与结果格式化

pub mod duckduckgo;

use std::collections::HashMap;
use std::sync::Arc;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Web seam 错误（机器可读 code 字符串与 harness `WebError` 对齐风格）。
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum WebError {
    #[error("web provider unavailable")]
    ProviderUnavailable,
    #[error("web provider `{0}` configured but missing")]
    ConfiguredMissing(String),
    #[error("web provider `{0}` configured but unavailable")]
    ConfiguredUnavailable(String),
    #[error("multiple usable web providers; set search_provider id")]
    ProviderAmbiguous,
    #[error("duplicate web provider id `{0}`")]
    DuplicateProvider(String),
    #[error("web provider error: {0}")]
    Provider(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebSearchRequest {
    pub query: String,
    pub max_results: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WebSearchSource {
    pub url: String,
    pub title: Option<String>,
    pub snippet: Option<String>,
    pub published_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WebSearchResult {
    pub content: Option<String>,
    pub sources: Vec<WebSearchSource>,
    pub truncated: bool,
}

#[async_trait]
pub trait WebSearchProvider: Send + Sync {
    fn id(&self) -> &str;
    /// 廉价本地可用性检查；不得发网络请求。
    fn available(&self) -> bool;
    async fn search(&self, request: &WebSearchRequest) -> Result<WebSearchResult, WebError>;
}

/// Provider 注册与执行时选择（顺序无关；配置 id / 唯一可用 / 歧义报错）。
pub struct WebRuntime {
    search_providers: HashMap<String, Arc<dyn WebSearchProvider>>,
    configured_search_provider: Option<String>,
}

impl Default for WebRuntime {
    fn default() -> Self {
        Self::new(None)
    }
}

impl WebRuntime {
    pub fn new(configured_search_provider: Option<String>) -> Self {
        Self {
            search_providers: HashMap::new(),
            configured_search_provider: configured_search_provider
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty()),
        }
    }

    pub fn register_search_provider(
        &mut self,
        provider: Arc<dyn WebSearchProvider>,
    ) -> Result<(), WebError> {
        let id = provider.id().to_string();
        if self.search_providers.contains_key(&id) {
            return Err(WebError::DuplicateProvider(id));
        }
        self.search_providers.insert(id, provider);
        Ok(())
    }

    pub async fn search(&self, request: &WebSearchRequest) -> Result<WebSearchResult, WebError> {
        let provider = self.resolve_search_provider()?;
        let result = provider.search(request).await?;
        Ok(cap_sources(result, request.max_results))
    }

    fn resolve_search_provider(&self) -> Result<Arc<dyn WebSearchProvider>, WebError> {
        if let Some(id) = &self.configured_search_provider {
            let Some(provider) = self.search_providers.get(id) else {
                return Err(WebError::ConfiguredMissing(id.clone()));
            };
            if !provider.available() {
                return Err(WebError::ConfiguredUnavailable(id.clone()));
            }
            return Ok(Arc::clone(provider));
        }

        let usable: Vec<_> = self
            .search_providers
            .values()
            .filter(|p| p.available())
            .cloned()
            .collect();
        match usable.len() {
            0 => Err(WebError::ProviderUnavailable),
            1 => Ok(usable.into_iter().next().expect("len 1")),
            _ => Err(WebError::ProviderAmbiguous),
        }
    }
}

fn cap_sources(mut result: WebSearchResult, max: Option<usize>) -> WebSearchResult {
    let Some(max) = max else {
        return result;
    };
    if result.sources.len() > max {
        result.sources.truncate(max);
        result.truncated = true;
    }
    result
}

/// 默认运行时：注册 DuckDuckGo Instant Answer（经网络沙盒）。
pub fn default_web_runtime() -> WebRuntime {
    let mut runtime = WebRuntime::new(Some(duckduckgo::PROVIDER_ID.to_string()));
    let provider = Arc::new(duckduckgo::DuckDuckGoSearchProvider::default());
    let _ = runtime.register_search_provider(provider);
    runtime
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FakeProvider {
        id: &'static str,
        available: bool,
    }

    #[async_trait]
    impl WebSearchProvider for FakeProvider {
        fn id(&self) -> &str {
            self.id
        }
        fn available(&self) -> bool {
            self.available
        }
        async fn search(&self, _request: &WebSearchRequest) -> Result<WebSearchResult, WebError> {
            Ok(WebSearchResult {
                content: Some(format!("from {}", self.id)),
                sources: (0..12)
                    .map(|i| WebSearchSource {
                        url: format!("https://example.com/{i}"),
                        title: Some(format!("t{i}")),
                        snippet: None,
                        published_at: None,
                    })
                    .collect(),
                truncated: false,
            })
        }
    }

    #[tokio::test]
    async fn selects_configured_and_caps() {
        let mut runtime = WebRuntime::new(Some("a".into()));
        runtime
            .register_search_provider(Arc::new(FakeProvider {
                id: "a",
                available: true,
            }))
            .unwrap();
        runtime
            .register_search_provider(Arc::new(FakeProvider {
                id: "b",
                available: true,
            }))
            .unwrap();
        let result = runtime
            .search(&WebSearchRequest {
                query: "q".into(),
                max_results: Some(3),
            })
            .await
            .unwrap();
        assert_eq!(result.sources.len(), 3);
        assert!(result.truncated);
        assert_eq!(result.content.as_deref(), Some("from a"));
    }

    #[tokio::test]
    async fn ambiguous_without_config() {
        let mut runtime = WebRuntime::new(None);
        runtime
            .register_search_provider(Arc::new(FakeProvider {
                id: "a",
                available: true,
            }))
            .unwrap();
        runtime
            .register_search_provider(Arc::new(FakeProvider {
                id: "b",
                available: true,
            }))
            .unwrap();
        let err = runtime
            .search(&WebSearchRequest {
                query: "q".into(),
                max_results: None,
            })
            .await
            .unwrap_err();
        assert_eq!(err, WebError::ProviderAmbiguous);
    }
}
