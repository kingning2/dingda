//! Sidecar route binding: /v1/channel/cookie_renew (POST)
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19

use crate::contracts::contracts::{
    ChannelSidecarCookieRenewRequest, ChannelSidecarCookieRenewResponse,
};

use super::super::client::{SidecarClient, SidecarClientError};

/// 调用 sidecar 浏览器续期 Cookie。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
///
/// # 参数
/// - `client` — sidecar HTTP 客户端
/// - `request` — 账号与现有 Cookie
///
/// # 返回值
/// 续期结果；传输或 sidecar 失败返回错误。
pub async fn call(
    client: &SidecarClient,
    request: ChannelSidecarCookieRenewRequest,
) -> Result<ChannelSidecarCookieRenewResponse, SidecarClientError> {
    client.post_json("/v1/channel/cookie_renew", &request).await
}
