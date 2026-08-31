use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::Serialize;
use serde_json::Value;
use sqlx::FromRow;

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct Product {
    pub id: u64,
    pub name: String,
    pub brand: Option<String>,
    pub model: Option<String>,
    pub category_id: Option<u64>,
    pub description: Option<String>,
    pub cover_url: Option<String>,
    pub status: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct ProductPlatform {
    pub id: u64,
    pub product_id: u64,
    pub platform: String,
    pub platform_product_id: String,
    pub url: Option<String>,
    pub title: Option<String>,
    pub shop_id: Option<String>,
    pub shop_name: Option<String>,
    pub seller_id: Option<String>,
    pub status: String,
    pub first_seen_at: DateTime<Utc>,
    pub last_seen_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct ProductSnapshotRef {
    pub id: u64,
    pub product_platform_id: u64,
    pub snapshot_hash: String,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct ProductSnapshotRow {
    pub id: u64,
    pub product_platform_id: u64,
    pub crawl_task_id: u64,
    pub captured_at: DateTime<Utc>,
    pub title: Option<String>,
    pub subtitle: Option<String>,
    pub description: Option<String>,
    pub brand: Option<String>,
    pub category: Option<String>,
    pub attributes_json: Option<Value>,
    pub cover_url: Option<String>,
    pub snapshot_hash: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct PriceSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub product_platform_id: u64,
    pub currency: String,
    pub price: Option<Decimal>,
    pub original_price: Option<Decimal>,
    pub min_price: Option<Decimal>,
    pub max_price: Option<Decimal>,
    pub discount_amount: Option<Decimal>,
    pub coupon_amount: Option<Decimal>,
    pub shipping_fee: Option<Decimal>,
    pub price_text: Option<String>,
    pub captured_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct SalesSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub product_platform_id: u64,
    pub sales_count: Option<i64>,
    pub sales_period: Option<String>,
    pub sales_text: Option<String>,
    pub review_count: Option<i64>,
    pub rating: Option<Decimal>,
    pub favorite_count: Option<i64>,
    pub want_count: Option<i64>,
    pub view_count: Option<i64>,
    pub captured_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct SkuSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub platform_sku_id: Option<String>,
    pub sku_name: Option<String>,
    pub attributes_json: Option<Value>,
    pub price: Option<Decimal>,
    pub original_price: Option<Decimal>,
    pub stock: Option<i64>,
    pub sku_data_json: Option<Value>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct SellerSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub seller_id: Option<String>,
    pub shop_id: Option<String>,
    pub shop_name: Option<String>,
    pub seller_level: Option<String>,
    pub rating: Option<Decimal>,
    pub positive_rate: Option<Decimal>,
    pub follower_count: Option<i64>,
    pub transaction_count: Option<i64>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct ShippingSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub origin: Option<String>,
    pub destination: Option<String>,
    pub shipping_fee: Option<Decimal>,
    pub free_shipping: Option<i8>,
    pub delivery_time: Option<String>,
    pub fulfillment_type: Option<String>,
    pub shipping_data_json: Option<Value>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct ProductMediaSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub media_type: String,
    pub url: String,
    pub sort_order: i32,
    pub metadata_json: Option<Value>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct RawSnapshot {
    pub id: u64,
    pub product_snapshot_id: u64,
    pub platform: String,
    pub raw_data_json: Value,
    pub content_type: Option<String>,
    pub data_version: Option<String>,
    pub crawler_version: Option<String>,
    pub created_at: DateTime<Utc>,
}
