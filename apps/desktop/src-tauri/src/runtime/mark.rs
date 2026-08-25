//! Runtime 生命周期标记辅助 — 供 `#[runtime(...)]` 宏展开调用。
//!
//! 与 `#[timed]` → `crate::timing` 同层：宏 crate 不依赖业务类型。

use super::RUNTIME_TARGET;

/// 记录 `[runtime]` 相位日志。
///
/// - `python` / `agent` / … → `[runtime] {scope}.{phase}`
/// - `runtime`（Supervisor 全局）→ `[runtime] state={phase}`（与历史格式一致）
pub fn phase(scope: &str, phase: &str) {
    if scope == "runtime" {
        info!(target: RUNTIME_TARGET, "[runtime] state={phase}");
    } else {
        info!(target: RUNTIME_TARGET, "[runtime] {scope}.{phase}");
    }
}
