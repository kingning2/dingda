//! App 壳层：共享状态、生命周期观测、窗口/平台装配、日志与计时。

pub mod lifecycle;
pub mod logging;
pub mod startup;
pub mod startup_probe;
pub mod state;
pub mod timing;
pub mod window;

pub use logging::init_tracing;
pub use state::AppState;
pub use window::{platform_initialization_script, register_platform};
