//! 有锁构建但 verifier 不可用时的 fail-closed 闸门。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use crate::contracts::license::{LicenseActivateRequest, LicenseStatus};
use crate::ports::license::{LicenseError, LicenseGate};
use async_trait::async_trait;

/// Fail-closed 闸门：拒绝一切需授权操作。
///
/// 功能：
///
/// - 在 `license-lock` 开启但 verifier 初始化失败时使用
/// - 状态查询返回未激活，并暴露初始化错误原因
///
/// 作者：coisini
/// 创建时间：2026-07-16
pub struct FailClosedLicenseGate {
    /// 初始化失败原因，会写入 status.reason 与错误返回值。
    reason: String,
}

impl FailClosedLicenseGate {
    /// 使用初始化失败原因构造 fail-closed 闸门。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 参数
    ///
    /// * `reason` - verifier / 数据目录初始化失败的说明
    ///
    /// # 返回值
    ///
    /// 返回新的 [`FailClosedLicenseGate`]。
    pub fn new(reason: impl Into<String>) -> Self {
        Self {
            reason: reason.into(),
        }
    }

    fn fail_error(&self) -> LicenseError {
        LicenseError::FailClosed {
            reason: self.reason.clone(),
        }
    }
}

#[async_trait]
impl LicenseGate for FailClosedLicenseGate {
    async fn status(&self) -> Result<LicenseStatus, LicenseError> {
        Ok(LicenseStatus {
            gate_enabled: true,
            activated: false,
            reason: Some(self.reason.clone()),
            machine_code: None,
            expires_at: None,
            product: None,
        })
    }

    async fn machine_code(&self) -> Result<String, LicenseError> {
        Err(self.fail_error())
    }

    async fn activate(
        &self,
        _request: LicenseActivateRequest,
    ) -> Result<LicenseStatus, LicenseError> {
        Err(self.fail_error())
    }

    async fn ensure_licensed(&self) -> Result<(), LicenseError> {
        Err(self.fail_error())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn fail_closed_blocks_activation_and_business() {
        let gate = FailClosedLicenseGate::new("verifier missing");
        let status = gate.status().await.expect("status");
        assert!(status.gate_enabled);
        assert!(!status.activated);
        assert!(gate.ensure_licensed().await.is_err());
        assert!(gate
            .activate(LicenseActivateRequest {
                token: Some("x".into()),
                key_bytes_base64: None,
            })
            .await
            .is_err());
    }
}
