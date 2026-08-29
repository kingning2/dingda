//! Sidecar 渠道商品 RPC — 闲鱼商品详情 / 消息头信息 / 卖家在售 / 用户主页。
//!
//! 路由：`/v1/channel/xianyu/item_detail` · `message_headinfo` ·
//! `seller_items` · `user_profile`（均 POST）。

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::infrastructure::sidecar::client::{SidecarClient, SidecarClientError};

/// 商品详情（`/v1/channel/xianyu/item_detail`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ItemDetailRequest {
    pub cookie: String,
    pub item_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformItemDetailDto {
    pub item_id: String,
    pub title: String,
    pub desc: String,
    pub price: f64,
    pub original_price: Option<f64>,
    #[serde(default)]
    pub images: Vec<String>,
    pub want_count: Option<u32>,
    pub browse_count: Option<u32>,
    pub item_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ItemDetailResponse {
    pub ok: bool,
    #[serde(default)]
    pub detail: Option<PlatformItemDetailDto>,
    #[serde(default)]
    pub cookie: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn item_detail(
    client: &SidecarClient,
    request: ItemDetailRequest,
) -> Result<ItemDetailResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/item_detail", &request)
        .await
}

/// 消息头信息（`/v1/channel/xianyu/message_headinfo`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeadinfoRequest {
    pub cookie: String,
    pub session_id: String,
    #[serde(default)]
    pub item_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeadinfoResponse {
    pub ok: bool,
    #[serde(default)]
    pub data: Option<Value>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn message_headinfo(
    client: &SidecarClient,
    request: MessageHeadinfoRequest,
) -> Result<MessageHeadinfoResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/message_headinfo", &request)
        .await
}

/// 卖家在售商品（`/v1/channel/xianyu/seller_items`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SellerItemsRequest {
    pub cookie: String,
    pub user_id: String,
    #[serde(default)]
    pub max_pages: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformItemDto {
    pub item_id: String,
    pub title: String,
    pub price: f64,
    #[serde(default)]
    pub desc: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SellerItemsResponse {
    pub ok: bool,
    #[serde(default)]
    pub items: Vec<PlatformItemDto>,
    #[serde(default)]
    pub cookie: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn seller_items(
    client: &SidecarClient,
    request: SellerItemsRequest,
) -> Result<SellerItemsResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/seller_items", &request)
        .await
}

/// 用户主页（`/v1/channel/xianyu/user_profile`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserProfileRequest {
    pub cookie: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UserProfileDto {
    #[serde(default)]
    pub display_name: String,
    #[serde(default)]
    pub avatar_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserProfileResponse {
    pub ok: bool,
    #[serde(default)]
    pub profile: Option<UserProfileDto>,
    #[serde(default)]
    pub cookie: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn user_profile(
    client: &SidecarClient,
    request: UserProfileRequest,
) -> Result<UserProfileResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/user_profile", &request)
        .await
}
