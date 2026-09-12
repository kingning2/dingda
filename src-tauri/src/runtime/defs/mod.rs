// `pub(crate)`：`model_discover::modelsdev` 要复用 `base::fetch_text`。
pub(crate) mod base;
mod claude;
mod codex;
mod opencode;

pub use claude::CLAUDE;
pub use codex::CODEX;
pub use opencode::OPENCODE;
