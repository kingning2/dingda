//! 组件生命周期抽象 — 全仓库唯一定义。
//!
//! 任何需要启停 / 健康管理的组件（Python sidecar、Agent 运行时、
//! 渠道长连接……）实现本 trait 并注册到 [`super::RuntimeSupervisor`]，
//! 由其统一编排启动顺序、级联停止与状态上报；不得自行另建生命周期管理。

use std::time::Duration;

use async_trait::async_trait;

use crate::contracts::RuntimeComponentState;

/// 组件生命周期状态（契约 `runtime/component_state`）。
pub type ComponentState = RuntimeComponentState;

/// 健康检查结果。
#[derive(Debug, Clone)]
pub struct HealthReport {
    /// 是否健康。
    pub ok: bool,
    /// 补充说明（失败原因、重启次数等）。
    pub detail: Option<String>,
}

impl HealthReport {
    /// 健康结果。
    pub fn ok() -> Self {
        Self {
            ok: true,
            detail: None,
        }
    }

    /// 不健康结果。
    pub fn failed(detail: impl Into<String>) -> Self {
        Self {
            ok: false,
            detail: Some(detail.into()),
        }
    }
}

/// 组件 trait — start / stop / state / health。
#[async_trait]
pub trait Component: Send + Sync {
    /// 组件标识（如 `"python-sidecar"` / `"agent-runtime"`）。
    fn id(&self) -> &'static str;

    /// 当前生命周期状态。
    fn state(&self) -> ComponentState;

    /// 启动组件（幂等：已运行则直接成功）。
    async fn start(&self) -> Result<(), String>;

    /// 停止组件（幂等；重复调用为无操作）。
    async fn stop(&self) -> Result<(), String>;

    /// 健康检查。
    async fn health(&self) -> HealthReport;
}

/// 单组件停止超时（与原关闭策略一致）。
pub const STOP_TIMEOUT: Duration = Duration::from_secs(5);
