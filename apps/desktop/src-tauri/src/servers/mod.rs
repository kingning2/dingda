//! 渠道服务层 — 领域 / 协议 / 共享底座 / 存储 + 各站壳层。
//!
//! Tauri IPC 在 [`crate::command`]；风控判定与过滑块在 Python Sidecar。

pub mod core;
pub mod domain;
pub mod protocol;
pub mod runtime;
pub mod shared;
pub mod storage;

#[cfg(platform_xianyu)]
pub mod xianyu;
