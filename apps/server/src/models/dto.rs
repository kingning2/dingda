use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Deserialize)]
pub struct SnapshotBatchRequest {
    pub crawl_id: String,
    pub workspace_id: Option<u64>,
    pub snapshots: Vec<SnapshotInput>,
}

#[derive(Debug, Deserialize)]
pub struct SnapshotInput {
    pub snapshot_id: String,
    pub platform: String,
    pub captured_at: DateTime<Utc>,
    #[serde(default)]
    pub product: SnapshotProductDto,
    #[serde(default)]
    pub pricing: SnapshotPricingDto,
    #[serde(default)]
    pub sales: SnapshotSalesDto,
    #[serde(default)]
    pub seller: SnapshotSellerDto,
    #[serde(default)]
    pub shipping: SnapshotShippingDto,
    #[serde(default)]
    pub sku: Vec<SnapshotSkuDto>,
    #[serde(default)]
    pub media: Vec<SnapshotMediaDto>,
    #[serde(default)]
    pub raw: SnapshotRawDto,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotProductDto {
    pub platform_product_id: Option<String>,
    pub title: Option<String>,
    pub subtitle: Option<String>,
    pub description: Option<String>,
    pub brand: Option<String>,
    pub category: Option<String>,
    pub attributes: Option<Value>,
    pub cover_url: Option<String>,
    pub url: Option<String>,
    pub shop_id: Option<String>,
    pub shop_name: Option<String>,
    pub seller_id: Option<String>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotPricingDto {
    pub currency: Option<String>,
    pub price: Option<DecimalField>,
    pub original_price: Option<DecimalField>,
    pub min_price: Option<DecimalField>,
    pub max_price: Option<DecimalField>,
    pub discount_amount: Option<DecimalField>,
    pub coupon_amount: Option<DecimalField>,
    pub shipping_fee: Option<DecimalField>,
    pub price_text: Option<String>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotSalesDto {
    pub sales_count: Option<i64>,
    pub sales_period: Option<String>,
    pub sales_text: Option<String>,
    pub review_count: Option<i64>,
    pub rating: Option<f64>,
    pub favorite_count: Option<i64>,
    pub want_count: Option<i64>,
    pub view_count: Option<i64>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotSellerDto {
    pub seller_id: Option<String>,
    pub shop_id: Option<String>,
    pub shop_name: Option<String>,
    pub seller_level: Option<String>,
    pub rating: Option<f64>,
    pub positive_rate: Option<f64>,
    pub follower_count: Option<i64>,
    pub transaction_count: Option<i64>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotShippingDto {
    pub origin: Option<String>,
    pub destination: Option<String>,
    pub shipping_fee: Option<DecimalField>,
    pub free_shipping: Option<bool>,
    pub delivery_time: Option<String>,
    pub fulfillment_type: Option<String>,
    pub data: Option<Value>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotSkuDto {
    pub platform_sku_id: Option<String>,
    pub sku_name: Option<String>,
    pub attributes: Option<Value>,
    pub price: Option<DecimalField>,
    pub original_price: Option<DecimalField>,
    pub stock: Option<i64>,
    pub data: Option<Value>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotMediaDto {
    pub media_type: Option<String>,
    pub url: Option<String>,
    pub sort_order: Option<i32>,
    pub metadata: Option<Value>,
}

#[derive(Debug, Default, Deserialize, Serialize)]
pub struct SnapshotRawDto {
    pub data: Option<Value>,
    pub content_type: Option<String>,
    pub data_version: Option<String>,
    pub crawler_version: Option<String>,
}

#[derive(Debug, Clone, Copy, Deserialize, Serialize)]
#[serde(untagged)]
pub enum DecimalField {
    Number(f64),
}

impl DecimalField {
    pub fn to_sql_decimal(self) -> Option<rust_decimal::Decimal> {
        match self {
            DecimalField::Number(value) => rust_decimal::Decimal::from_f64_retain(value),
        }
    }
}

#[derive(Debug, Serialize)]
pub struct SnapshotBatchResponse {
    pub accepted: usize,
    pub duplicated: usize,
    pub failed: usize,
    pub results: Vec<SnapshotIngestResult>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SnapshotIngestStatus {
    Created,
    Duplicate,
    Failed,
}

#[derive(Debug, Serialize)]
pub struct SnapshotIngestResult {
    pub snapshot_id: String,
    pub status: SnapshotIngestStatus,
    pub product_snapshot_id: Option<u64>,
    pub product_platform_id: Option<u64>,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct CreateCrawlTaskInput {
    pub client_ref: String,
    pub platform: String,
    pub discovery_task_id: Option<u64>,
    pub workspace_id: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub struct ListQuery {
    pub offset: Option<u64>,
    pub limit: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub struct PlatformListQuery {
    pub platform: String,
    pub offset: Option<u64>,
    pub limit: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub struct SnapshotListQuery {
    pub product_platform_id: u64,
    pub offset: Option<u64>,
    pub limit: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub struct RegisterInput {
    pub email: String,
    pub password: String,
    pub name: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LoginInput {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Serialize)]
pub struct AuthResponse {
    pub token: String,
    pub expires_at: DateTime<Utc>,
    pub user: super::entity::UserPublic,
    pub workspace_id: u64,
}
