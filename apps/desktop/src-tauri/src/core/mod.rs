//! 核心业务层 — 领域 / 协议 / 存储 / 底座 / 运行时编排。
//!
//! Tauri IPC 在 [`crate::cmd`]；平台功能编排在 [`crate::feat`]。
//! `manager` 为运行时编排（Python / Agent / Task / Supervisor + App 生命周期）。

pub mod bootstrap;
pub mod channel;
pub mod domain;
pub mod infra;
pub mod manager;
pub mod platform;
pub mod ports;
pub mod protocol;
pub mod storage;
pub mod store;
