//! Python Server 子进程的生命周期与启动环境。
//!
//! 职责：
//!     拉起 / 探活 / 停止 `uvicorn`，并把 Server 需要的环境变量备齐。
//!
//! 设计说明：
//!     - `lifecycle` 管进程与 `/health` 探活
//!     - `env` 只算环境变量（国内镜像、uv、venv、Camoufox exe），不碰进程
//!     - Camoufox 解压走 `resolve_camoufox_env`，由壳在后台 `spawn_blocking`，
//!       禁止进 setup 主线程
//!     - `desktop_runtime_env` 原本放在 paths 包，因它是「给 Python 子进程准备环境」
//!       的 Python 关注点，迁入本包以打断 paths ↔ camoufox 的循环依赖

mod env;
mod lifecycle;

pub use env::{desktop_runtime_env, resolve_camoufox_env};
pub use lifecycle::{EventSink, PythonConfig, PythonLifecycle, PythonLifecycleError};
