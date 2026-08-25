//! App Lifecycle — Tauri App 本身的生命周期（观测层，只记录）。
//!
//! 对应前端 `apps/desktop/src/lifecycle/`：
//!
//! | kind | Rust 入口 |
//! |------|-----------|
//! | `app.start` | [`lifecycle::on_setup`] |
//! | `app.exit` | [`lifecycle::on_exit`] |
//! | `startup.phase` | [`startup::phase`] |
//! | Tauri `RunEvent` | [`lifecycle::on_run_ready`] 等 `on_run_*` |
//! | Tauri `on_page_load` | [`lifecycle::on_page_load`] |
//! | Tauri `on_window_event` | [`lifecycle::on_window_event`] |
//! | setup 阶段 | [`lifecycle::on_setup_begin`] 等 `on_*_ready` |
//! | `route.change` | [`route::on_route_change`] |
//!
//! `lib.rs` 仅负责注册 Tauri 钩子并转发到本模块；运行控制见 [`super::supervisor`]。

pub mod lifecycle;
pub mod route;
pub mod startup;

pub use lifecycle::{on_exit, on_setup};
