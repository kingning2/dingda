//! 应用运行时状态组装。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use crate::runtime::python::{RuntimeAgentSidecar, SidecarLifecycle};
use crate::runtime::RuntimeSupervisor;
use infra::event::InMemoryEventBus;
#[cfg(not(feature = "license-lock"))]
use infra::license::UnlockedLicenseGate;
#[cfg(feature = "license-lock")]
use infra::license::{FailClosedLicenseGate, VerifierProcessLicense};
use ports::license::LicenseGate;
use std::sync::Arc;

/// 桌面应用共享状态。
///
/// 功能：
///
/// - 持有 sidecar 生命周期与 Agent 网关
/// - 持有 License 闸门实现
/// - 持有进程内事件总线
/// - 持有 Runtime 总协调器（控制层；App 观测走 `runtime::app`）
///
/// 作者：coisini
/// 创建时间：2026-07-16
#[derive(Clone)]
pub struct AppState {
    /// Sidecar 生命周期控制器。
    pub lifecycle: Arc<SidecarLifecycle>,
    /// Agent sidecar 网关适配器。
    pub gateway: Arc<RuntimeAgentSidecar>,
    /// License 闸门（无锁 stub 或 verifier / fail-closed）。
    pub license: Arc<dyn LicenseGate>,
    /// 进程内事件总线（runtime.* 事件经 BusToTauri 转发到前端）。
    pub event_bus: Arc<InMemoryEventBus>,
    /// Runtime 总协调器（Python / Agent / Task / Shutdown）。
    pub supervisor: Arc<RuntimeSupervisor>,
}

/// 按 Cargo feature 构造 License 闸门。
///
/// 功能：
///
/// - 无 `license-lock`：返回 [`UnlockedLicenseGate`]
/// - 有 `license-lock`：优先 [`VerifierProcessLicense`]，失败则 fail-closed
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 返回值
///
/// 返回可共享的 [`LicenseGate`] trait 对象。
pub fn build_license_gate() -> Arc<dyn LicenseGate> {
    #[cfg(feature = "license-lock")]
    {
        match VerifierProcessLicense::from_env() {
            Ok(gate) => Arc::new(gate),
            Err(error) => {
                error!(%error, "已启用授权锁但校验器不可用");
                Arc::new(FailClosedLicenseGate::new(error.to_string()))
            }
        }
    }
    #[cfg(not(feature = "license-lock"))]
    {
        Arc::new(UnlockedLicenseGate::new())
    }
}
