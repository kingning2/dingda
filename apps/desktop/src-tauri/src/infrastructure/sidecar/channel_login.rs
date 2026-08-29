//! Sidecar 渠道登录 RPC — 扫码启停 / 状态轮询 / 登录探针 / Cookie 续期。
//!
//! 路由：`/v1/channel/qr_start` · `qr_check` · `qr_cancel` ·
//! `login_probe` · `cookie_renew`（均 POST）。

use crate::contracts::{
    ChannelSidecarCookieRenewRequest, ChannelSidecarCookieRenewResponse,
    ChannelSidecarLoginProbeRequest, ChannelSidecarLoginProbeResponse,
    ChannelSidecarQrCancelRequest, ChannelSidecarQrCancelResponse, ChannelSidecarQrCheckRequest,
    ChannelSidecarQrCheckResponse, ChannelSidecarQrStartRequest, ChannelSidecarQrStartResponse,
};
use crate::infrastructure::sidecar::client::{SidecarClient, SidecarClientError};

/// 扫码登录 — 获取二维码（`/v1/channel/qr_start`）。
pub async fn qr_start(
    client: &SidecarClient,
    request: ChannelSidecarQrStartRequest,
) -> Result<ChannelSidecarQrStartResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_start", &request).await
}

/// 扫码登录 — 轮询扫码状态（`/v1/channel/qr_check`）。
pub async fn qr_check(
    client: &SidecarClient,
    request: ChannelSidecarQrCheckRequest,
) -> Result<ChannelSidecarQrCheckResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_check", &request).await
}

/// 扫码登录 — 取消（`/v1/channel/qr_cancel`）。
pub async fn qr_cancel(
    client: &SidecarClient,
    request: ChannelSidecarQrCancelRequest,
) -> Result<ChannelSidecarQrCancelResponse, SidecarClientError> {
    client.post_json("/v1/channel/qr_cancel", &request).await
}

/// 登录态探针（`/v1/channel/login_probe`）。
pub async fn login_probe(
    client: &SidecarClient,
    request: ChannelSidecarLoginProbeRequest,
) -> Result<ChannelSidecarLoginProbeResponse, SidecarClientError> {
    client.post_json("/v1/channel/login_probe", &request).await
}

/// 调用 sidecar 浏览器续期 Cookie（`/v1/channel/cookie_renew`）。
///
/// # 参数
/// - `client` — sidecar HTTP 客户端
/// - `request` — 账号与现有 Cookie
///
/// # 返回值
/// 续期结果；传输或 sidecar 失败返回错误。
pub async fn cookie_renew(
    client: &SidecarClient,
    request: ChannelSidecarCookieRenewRequest,
) -> Result<ChannelSidecarCookieRenewResponse, SidecarClientError> {
    client.post_json("/v1/channel/cookie_renew", &request).await
}
