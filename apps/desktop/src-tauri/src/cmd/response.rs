//! 统一 IPC 响应结构。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use serde::Serialize;

/// 前后端统一 IPC 响应体。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, Serialize)]
pub struct IpcResponse<T>
where
    T: Serialize,
{
    /// 业务状态码（成功固定 200）。
    pub code: u16,
    /// 响应消息（成功默认 ok）。
    pub message: String,
    /// 实际业务数据。
    pub data: T,
}

impl<T> IpcResponse<T>
where
    T: Serialize,
{
    /// 构造成功响应。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    ///
    /// * `data` - 业务数据
    ///
    /// # 返回值
    ///
    /// code=200 的统一响应结构。
    pub fn ok(data: T) -> Self {
        Self {
            code: 200,
            message: "ok".to_string(),
            data,
        }
    }
}
