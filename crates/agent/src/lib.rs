//! agent crate — AI 编排层。
//!
//! 在 `lib` 编排：`intent` → `knowledge` → `prompt` → `model` → `reply`。
//! 各功能为独立文件夹（`model` / `knowledge` / `prompt` / `intent` / `reply`），
//! 各自负责各自功能；本 lib 负责编排与策略（议价控制、provider 分发）。
//!
//! - `model` — LLM 模型家族（seam + 4 个 provider）
//! - `knowledge` — 知识库（商品信息提取与注入）
//! - `prompt` — 提示词模板（模板独立文件 + 意图索引）
//! - `intent` — 本地意图检测（price / tech / default / no_reply）
//! - `reply` — 回复引擎（编排入口：`ReplyEngine::generate`）
//! - `web` / `sandbox` / `tools` / `tool_loop` — 联网搜索与 tool_calls 循环

#[macro_use]
extern crate tracing;

pub mod intent;
pub mod knowledge;
pub mod model;
pub mod prompt;
pub mod reply;
pub mod sandbox;
pub mod tool_loop;
pub mod tools;
pub mod web;
pub mod web_assist;

pub use intent::{route_intent, Intent};
pub use knowledge::{build_item_context, ItemKnowledge};
pub use model::{
    clean_text, normalize_provider_type, provider_from_settings, AssistantToolCall, ChatMessage,
    ChatRequest, ChatResponse, LlmError, LlmProvider, ProviderSettings, ToolSpec,
};
pub use prompt::PromptBuilder;
pub use reply::{AiSettings, ReplyContext, ReplyEngine, ReplyOutcome};
pub use tool_loop::{run as run_tool_loop, ToolLoopConfig, ToolLoopOutcome, ToolTraceEntry};
pub use web_assist::{inject_web_context, WebSearchBundle};
