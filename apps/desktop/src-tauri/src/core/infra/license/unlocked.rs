//! 无锁构建的 License 闸门适配器。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use crate::contracts::license::{LicenseActivateRequest, LicenseStatus};
use crate::core::ports::license::{LicenseError, LicenseGate};
use async_trait::async_trait;

/// 无锁构建使用的短路闸门。
///
/// 功能：
///
/// - 始终报告已激活且闸门关闭
/// - 不依赖 license-verifier 二进制
///
/// 作者：coisini
/// 创建时间：2026-07-16
pub struct UnlockedLicenseGate;

impl UnlockedLicenseGate {
    /// 构造无锁闸门实例。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 返回值
    ///
    /// 返回新的 [`UnlockedLicenseGate`]。
    pub fn new() -> Self {
        Self
    }

    fn unlocked_status() -> LicenseStatus {
        LicenseStatus {
            gate_enabled: false,
            activated: true,
            reason: None,
            machine_code: None,
            expires_at: None,
            product: None,
        }
    }
}

impl Default for UnlockedLicenseGate {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl LicenseGate for UnlockedLicenseGate {
    async fn status(&self) -> Result<LicenseStatus, LicenseError> {
        Ok(Self::unlocked_status())
    }

    async fn machine_code(&self) -> Result<String, LicenseError> {
        Ok("unlocked-build".to_string())
    }

    async fn activate(
        &self,
        _request: LicenseActivateRequest,
    ) -> Result<LicenseStatus, LicenseError> {
        Ok(Self::unlocked_status())
    }

    async fn ensure_licensed(&self) -> Result<(), LicenseError> {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn unlocked_gate_reports_activated_without_gate() {
        let gate = UnlockedLicenseGate::new();
        let status = gate.status().await.expect("status");
        assert!(!status.gate_enabled);
        assert!(status.activated);
        gate.ensure_licensed().await.expect("ensure");
    }
}
