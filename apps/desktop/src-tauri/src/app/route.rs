//! 路由切换生命周期 — 前端 invoke 后 Rust 侧写 tracing。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

/// 记录工作区路由访问（由 `log_write` IPC 或内部调用）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
///
/// * `message` — 已格式化的访问描述
pub fn on_route_change(message: &str) {
    info!(target: "dingda.lifecycle", "{message}");
}
