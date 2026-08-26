//! App 壳层：共享状态、生命周期观测、平台装配、日志与计时。

pub mod lifecycle;
pub mod logging;
pub mod platform;
pub mod route;
pub mod shell_platform;
pub mod startup;
pub mod state;
pub mod timing;

pub use logging::init_tracing;
pub use shell_platform::platform_initialization_script;
pub use state::AppState;
