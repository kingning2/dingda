//! 平台功能编排层 — 各渠道站壳（feature orchestration）。
//!
//! Tauri IPC 在 [`crate::cmd`]；风控判定与过滑块在 Python Sidecar。

#[cfg(platform_xianyu)]
pub mod xianyu;
