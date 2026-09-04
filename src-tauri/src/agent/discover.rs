use std::path::PathBuf;

use crate::runtime::{resolve_executable, RuntimeDefinition};

/// 发现 Agent CLI 可执行文件路径 — 委托统一 `resolve_executable()`。
pub fn discover_agent(definition: &RuntimeDefinition) -> Option<PathBuf> {
    resolve_executable(definition).map(|resolved| resolved.path)
}

pub fn discover_agent_with_source(
    definition: &RuntimeDefinition,
) -> Option<(PathBuf, crate::runtime::ExecutableSource)> {
    resolve_executable(definition).map(|resolved| (resolved.path, resolved.source))
}
