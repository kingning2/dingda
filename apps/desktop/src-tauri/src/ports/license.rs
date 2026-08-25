//! License gate port — activation / machine-code boundary.
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use crate::contracts::license::{LicenseActivateRequest, LicenseStatus};
use async_trait::async_trait;
use thiserror::Error;

/// License 闸门领域错误。
///
/// 功能：
///
/// - 统一描述激活、机器码、verifier 子进程失败原因
/// - 错误文案包含「何处 / 为何 / 如何解决」
///
/// 作者：coisini
/// 创建时间：2026-07-16
#[derive(Debug, Clone, Error)]
pub enum LicenseError {
    /// 本地 license 数据目录不可用。
    #[error(
        "license data directory unavailable ({detail}). \
         Set DINGDA_LICENSE_DIR or ensure APPDATA/HOME exists"
    )]
    DataDirUnavailable {
        /// 失败细节（路径或环境变量缺失说明）。
        detail: String,
    },

    /// 找不到 license-verifier 可执行文件。
    #[error(
        "license-verifier not found ({detail}). \
         Run `pnpm build:license-verifier` or set LICENSE_VERIFIER_EXE"
    )]
    VerifierNotFound {
        /// 查找路径或环境变量说明。
        detail: String,
    },

    /// 启动 verifier 子进程失败。
    #[error(
        "failed to spawn license-verifier at {path}: {cause}. \
         Check binary permissions and that the path points to a valid executable"
    )]
    SpawnFailed {
        /// verifier 可执行文件路径。
        path: String,
        /// 底层 IO 错误信息。
        cause: String,
    },

    /// verifier 进程返回运行时错误（通常 exit = 2）。
    #[error(
        "license-verifier runtime error (exit {exit}): {detail}. \
         Inspect verifier logs and license artifacts under the app data directory"
    )]
    VerifierRuntime {
        /// 进程退出码。
        exit: i32,
        /// stdout / stderr 摘要。
        detail: String,
    },

    /// 解析 verifier JSON 输出失败。
    #[error(
        "parse license-verifier JSON failed: {cause}; stdout={stdout}. \
         Ensure verifier version matches the expected JSON schema"
    )]
    ParseFailed {
        /// serde 错误信息。
        cause: String,
        /// 原始 stdout，便于排障。
        stdout: String,
    },

    /// 激活请求参数不合法（token 与 key 必须二选一）。
    #[error(
        "invalid activation request: provide exactly one of token or keyBytesBase64. \
         Clear the unused field and retry"
    )]
    InvalidActivateRequest,

    /// Base64 解码失败。
    #[error(
        "keyBytesBase64 decode failed: {cause}. \
         Re-export the .key file and ensure it is sent as standard Base64"
    )]
    KeyDecodeFailed {
        /// 解码错误信息。
        cause: String,
    },

    /// 本地文件读写失败。
    #[error(
        "license file IO failed while {operation} at {path}: {cause}. \
         Check disk permissions and free space"
    )]
    IoFailed {
        /// 操作名称（read / write / remove / create_dir）。
        operation: String,
        /// 目标路径。
        path: String,
        /// 底层错误信息。
        cause: String,
    },

    /// 磁盘上没有可用的 key / token。
    #[error(
        "no license key or token on disk. \
         Activate with a .key file or pasted token first"
    )]
    MissingLicenseArtifact,

    /// license.token 为空。
    #[error(
        "license.token is empty at {path}. \
         Delete the file and activate again with a valid token"
    )]
    EmptyToken {
        /// token 文件路径。
        path: String,
    },

    /// verifier 返回空 stdout。
    #[error(
        "license-verifier returned empty stdout (exit {exit}). \
         Rebuild the verifier binary and retry"
    )]
    EmptyVerifierStdout {
        /// 进程退出码。
        exit: i32,
    },

    /// 激活被拒绝（验签失败、过期、机器码不匹配等）。
    #[error(
        "activation rejected: {reason}. \
         Confirm the machine code matches the issued license and that the license has not expired"
    )]
    ActivationRejected {
        /// verifier / 业务拒绝原因。
        reason: String,
    },

    /// 当前未授权，业务 IPC 被拒绝。
    #[error(
        "license required: {reason}. \
         Open the activation panel and import a valid license"
    )]
    NotLicensed {
        /// 未授权原因。
        reason: String,
    },

    /// Fail-closed：有锁构建但 verifier 不可用。
    #[error(
        "license gate fail-closed: {reason}. \
         Bundle license-verifier or set LICENSE_VERIFIER_EXE, then restart"
    )]
    FailClosed {
        /// 初始化失败原因。
        reason: String,
    },

    /// verifier 二进制完整性校验失败。
    #[error(
        "license-verifier integrity check failed at {path}: expected sha256 {expected}, got {actual}. \
         Rebuild with `pnpm build:license-verifier` and do not replace the bundled binary"
    )]
    IntegrityFailed {
        /// 二进制路径。
        path: String,
        /// 期望哈希。
        expected: String,
        /// 实际哈希。
        actual: String,
    },

    /// 挑战应答 attestation 校验失败。
    #[error(
        "license attestation failed: {detail}. \
         Use the official license-verifier build; forged or patched binaries are rejected"
    )]
    AttestationFailed {
        /// 失败细节。
        detail: String,
    },
}

/// License 闸门端口。
///
/// 功能：
///
/// - 查询激活状态与设备码
/// - 写入并校验激活 token / `.key`
/// - 业务 IPC 前做硬授权检查
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 注意事项
///
/// - 无锁构建应始终返回已激活且 `gate_enabled = false`
/// - 有锁构建在 verifier 缺失时必须 fail-closed
#[async_trait]
pub trait LicenseGate: Send + Sync {
    /// 查询当前授权状态。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 返回值
    ///
    /// 成功返回 [`LicenseStatus`]；失败返回 [`LicenseError`]。
    async fn status(&self) -> Result<LicenseStatus, LicenseError>;

    /// 读取本机设备码。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 返回值
    ///
    /// 成功返回设备码字符串；失败返回 [`LicenseError`]。
    async fn machine_code(&self) -> Result<String, LicenseError>;

    /// 使用 token 或 `.key` 字节激活。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 参数
    ///
    /// * `request` - 激活请求，`token` 与 `key_bytes_base64` 必须二选一
    ///
    /// # 返回值
    ///
    /// 成功返回激活后的 [`LicenseStatus`]；失败返回 [`LicenseError`]。
    async fn activate(
        &self,
        request: LicenseActivateRequest,
    ) -> Result<LicenseStatus, LicenseError>;

    /// 确保当前已授权，供业务 IPC 调用。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 返回值
    ///
    /// 已授权返回 `Ok(())`；未授权返回 [`LicenseError::NotLicensed`] 等。
    async fn ensure_licensed(&self) -> Result<(), LicenseError>;
}
