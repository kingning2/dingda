//! License / activation DTOs（手写；Contract codegen 暂缓，避免 Python 生成物 churn）。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use serde::{Deserialize, Serialize};

/// 授权状态 DTO，经 Tauri IPC 暴露给前端。
///
/// 功能：
///
/// - 描述闸门是否开启、是否已激活
/// - 携带设备码、过期时间与产品名（可选）
///
/// 作者：coisini
/// 创建时间：2026-07-16
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LicenseStatus {
    /// 是否启用授权闸门（有锁构建为 `true`）。
    pub gate_enabled: bool,
    /// 当前是否已通过校验。
    pub activated: bool,
    /// 未激活或校验失败时的人类可读原因。
    pub reason: Option<String>,
    /// 本机设备码；无锁构建可为 `None`。
    pub machine_code: Option<String>,
    /// 授权过期时间（Unix 秒）；未知时为 `None`。
    pub expires_at: Option<i64>,
    /// 签发时绑定的产品名。
    pub product: Option<String>,
}

/// 激活请求 DTO。
///
/// 功能：
///
/// - 支持粘贴 token 或上传 `.key`（Base64）
/// - 两者必须恰好提供其一
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 示例
///
/// ```ignore
/// let by_token = LicenseActivateRequest {
///     token: Some("eyJ...".into()),
///     key_bytes_base64: None,
/// };
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LicenseActivateRequest {
    /// 粘贴的激活 token（claims JSON，通常为 base64url）。
    pub token: Option<String>,
    /// `.key` 文件原始字节的标准 Base64 编码。
    pub key_bytes_base64: Option<String>,
}
