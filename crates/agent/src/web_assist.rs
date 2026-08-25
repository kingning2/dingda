//! 便捷入口：构造默认 web + tools，执行一次 `web_search`。

use std::sync::Arc;

use crate::tools::{default_tool_runtime, ToolCall, ToolResult, ToolRuntime};
use crate::web::{default_web_runtime, WebRuntime};

/// 捆绑默认 WebRuntime 与 ToolRuntime（DuckDuckGo + 网络沙盒）。
pub struct WebSearchBundle {
    pub web: Arc<WebRuntime>,
    pub tools: ToolRuntime,
}

impl WebSearchBundle {
    pub fn default_bundle() -> Self {
        let web = Arc::new(default_web_runtime());
        let tools = default_tool_runtime(Arc::clone(&web));
        Self { web, tools }
    }

    pub async fn search(&self, query: &str) -> ToolResult {
        self.tools
            .invoke(&ToolCall {
                name: "web_search".into(),
                arguments: serde_json::json!({ "query": query }),
            })
            .await
    }
}

/// 将联网结果注入提示词（监控 AI 等单次 complete 场景）。
pub fn inject_web_context(prompt: &str, search_content: &str) -> String {
    let search_content = search_content.trim();
    if search_content.is_empty() {
        return prompt.to_string();
    }
    format!(
        "{prompt}\n\n---\n以下是经沙盒隔离的联网搜索结果（仅供参考，请结合商品信息判断；引用时使用 markdown 链接）：\n{search_content}\n---"
    )
}
