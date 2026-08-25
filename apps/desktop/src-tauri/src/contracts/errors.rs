//! DingDa 全局错误类型与 `Result` 别名。
//!
//! 负责：
//! - 跨层统一错误枚举 [`DingDaError`]
//! - 便捷构造方法与 IPC 字符串转换
//! - 与 [`anyhow`] 的边界层互转（壳层日志、上下文链）
//!
//! 各 crate 可继续保留领域错误（`StoreError`、`ChannelError` 等），
//! 在 Application / IPC 边界通过 [`DingDaError::wrap`] 或 `map_err` 汇总。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use serde::ser::Serializer;
use serde::Serialize;
use thiserror::Error;

/// DingDa 跨层统一错误枚举。
///
/// 按失败语义分类，便于日志过滤与 IPC 出口统一转 `String`。
/// 底层 IO / JSON 错误通过 `#[from]` 自动转换。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Error)]
pub enum DingDaError {
    /// 资源或实体不存在。
    #[error("not found: {resource} ({detail})")]
    NotFound {
        /// 资源类型（如 `account`、`order`）。
        resource: String,
        /// 具体标识或补充说明。
        detail: String,
    },

    /// 输入校验失败。
    #[error("validation failed: {0}")]
    Validation(String),

    /// 状态冲突（重复创建、乐观锁、幂等键冲突等）。
    #[error("conflict: {0}")]
    Conflict(String),

    /// 依赖不可用（存储、网络、子进程、License verifier 等）。
    #[error("unavailable: {service} — {detail}")]
    Unavailable {
        /// 不可用组件名称。
        service: String,
        /// 失败细节与修复提示。
        detail: String,
    },

    /// 未授权、权限不足或 License 未激活。
    #[error("unauthorized: {0}")]
    Unauthorized(String),

    /// 请求或操作超时。
    #[error("timeout: {0}")]
    Timeout(String),

    /// 序列化 / 反序列化失败（非 JSON 场景用字符串描述）。
    #[error("serialization: {0}")]
    Serialization(String),

    /// 渠道与协议层错误。
    #[error("channel: {0}")]
    Channel(String),

    /// 持久化与存储层错误。
    #[error("store: {0}")]
    Store(String),

    /// License 闸门错误。
    #[error("license: {0}")]
    License(String),

    /// 运行时、Sidecar 或 Agent 错误。
    #[error("runtime: {0}")]
    Runtime(String),

    /// 内部或未分类错误。
    #[error("internal: {0}")]
    Internal(String),

    /// 透传底层 `std::io::Error`。
    #[error("io: {0}")]
    Io(#[from] std::io::Error),

    /// 透传 `serde_json` 序列化错误。
    #[error("json: {0}")]
    Json(#[from] serde_json::Error),
}

/// 全局 `Result` 别名，默认错误类型为 [`DingDaError`]。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
pub type Result<T> = std::result::Result<T, DingDaError>;

impl DingDaError {
    /// 构造「不存在」错误。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `resource` — 资源类型名
    /// - `detail` — 标识或说明
    ///
    /// # 返回值
    /// [`DingDaError::NotFound`] 实例。
    pub fn not_found(resource: impl Into<String>, detail: impl Into<String>) -> Self {
        Self::NotFound {
            resource: resource.into(),
            detail: detail.into(),
        }
    }

    /// 构造校验失败错误。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn validation(message: impl Into<String>) -> Self {
        Self::Validation(message.into())
    }

    /// 构造冲突错误。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn conflict(message: impl Into<String>) -> Self {
        Self::Conflict(message.into())
    }

    /// 构造依赖不可用错误。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn unavailable(service: impl Into<String>, detail: impl Into<String>) -> Self {
        Self::Unavailable {
            service: service.into(),
            detail: detail.into(),
        }
    }

    /// 构造内部错误。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn internal(message: impl Into<String>) -> Self {
        Self::Internal(message.into())
    }

    /// 构造渠道 / 协议层错误。
    pub fn channel(message: impl Into<String>) -> Self {
        Self::Channel(message.into())
    }

    /// 构造存储层错误。
    pub fn store(message: impl Into<String>) -> Self {
        Self::Store(message.into())
    }

    /// 将任意可显示错误包装为内部错误（领域错误边界汇总）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `err` — 源错误（`Display` 文案写入 `Internal`）
    ///
    /// # 返回值
    /// [`DingDaError::Internal`]
    pub fn wrap<E: std::fmt::Display>(err: E) -> Self {
        Self::Internal(err.to_string())
    }

    /// 转为 Tauri IPC / 前端可展示的字符串（等同 `to_string()`）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn to_ipc_string(&self) -> String {
        self.to_string()
    }

    /// 附加上下文前缀，返回新的内部错误。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `context` — 上下文说明（如操作名、账号 ID）
    pub fn with_context(self, context: impl Into<String>) -> Self {
        Self::Internal(format!("{}: {}", context.into(), self))
    }
}

impl From<String> for DingDaError {
    fn from(value: String) -> Self {
        Self::Internal(value)
    }
}

impl From<&str> for DingDaError {
    fn from(value: &str) -> Self {
        Self::Internal(value.to_string())
    }
}

impl Serialize for DingDaError {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

/// 将 [`DingDaError`] 转为 [`anyhow::Error`]，便于壳层日志链与 `.context()`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
/// - `err` — 结构化错误
///
/// # 返回值
/// 可继续用 `anyhow` 追加上下文的错误对象。
pub fn to_anyhow(err: DingDaError) -> anyhow::Error {
    anyhow::Error::from(err)
}

/// 将 [`anyhow::Error`] 收拢为 [`DingDaError::Internal`]（丢失类型信息，仅用于最外层出口）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
pub fn from_anyhow(err: anyhow::Error) -> DingDaError {
    DingDaError::Internal(err.to_string())
}

/// 为 `Result` 附加上下文；失败时将原错误与 `context` 合并为 `Internal`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
/// - `result` — 原始结果
/// - `context` — 失败时前缀说明
pub fn with_context<T>(result: Result<T>, context: impl Into<String>) -> Result<T> {
    result.map_err(|err| err.with_context(context))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_not_found() {
        let err = DingDaError::not_found("account", "id=42");
        assert_eq!(err.to_string(), "not found: account (id=42)");
    }

    #[test]
    fn json_error_from() {
        let json_err = serde_json::from_str::<serde_json::Value>("not-json").unwrap_err();
        let err = DingDaError::from(json_err);
        assert!(matches!(err, DingDaError::Json(_)));
    }

    #[test]
    fn anyhow_roundtrip() {
        let original = DingDaError::validation("bad cookie");
        let anyhow_err = to_anyhow(original);
        let restored = from_anyhow(anyhow_err);
        assert!(matches!(restored, DingDaError::Internal(_)));
    }
}
