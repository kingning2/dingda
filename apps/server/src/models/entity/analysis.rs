use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde_json::Value;
use sqlx::FromRow;

#[derive(Debug, Clone, FromRow)]
pub struct ProductCost {
    pub id: u64,
    pub workspace_id: u64,
    pub product_id: u64,
    pub source_product_platform_id: u64,
    pub purchase_price: Option<Decimal>,
    pub shipping_cost: Option<Decimal>,
    pub packaging_cost: Option<Decimal>,
    pub platform_fee: Option<Decimal>,
    pub payment_fee: Option<Decimal>,
    pub advertising_cost: Option<Decimal>,
    pub after_sales_cost: Option<Decimal>,
    pub tax_cost: Option<Decimal>,
    pub other_cost: Option<Decimal>,
    pub effective_from: Option<DateTime<Utc>>,
    pub effective_to: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct ProfitAnalysis {
    pub id: u64,
    pub workspace_id: u64,
    pub product_id: u64,
    pub source_product_platform_id: u64,
    pub target_product_platform_id: Option<u64>,
    pub source_price: Option<Decimal>,
    pub target_price: Option<Decimal>,
    pub purchase_cost: Option<Decimal>,
    pub shipping_cost: Option<Decimal>,
    pub platform_fee: Option<Decimal>,
    pub payment_fee: Option<Decimal>,
    pub advertising_cost: Option<Decimal>,
    pub after_sales_cost: Option<Decimal>,
    pub tax_cost: Option<Decimal>,
    pub other_cost: Option<Decimal>,
    pub estimated_profit: Option<Decimal>,
    pub profit_margin: Option<Decimal>,
    pub estimated_sales: Option<i64>,
    pub estimated_revenue: Option<Decimal>,
    pub estimated_monthly_profit: Option<Decimal>,
    pub calculation_version: String,
    pub calculated_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct MarketAnalysis {
    pub id: u64,
    pub workspace_id: u64,
    pub product_id: u64,
    pub demand_score: Option<Decimal>,
    pub competition_score: Option<Decimal>,
    pub price_stability_score: Option<Decimal>,
    pub sales_growth_score: Option<Decimal>,
    pub estimated_monthly_sales: Option<i64>,
    pub estimated_monthly_revenue: Option<Decimal>,
    pub calculation_version: String,
    pub calculated_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct Opportunity {
    pub id: u64,
    pub workspace_id: u64,
    pub product_id: u64,
    pub source_platform: Option<String>,
    pub target_platform: Option<String>,
    pub estimated_profit: Option<Decimal>,
    pub profit_margin: Option<Decimal>,
    pub estimated_monthly_profit: Option<Decimal>,
    pub demand_score: Option<Decimal>,
    pub competition_score: Option<Decimal>,
    pub stability_score: Option<Decimal>,
    pub opportunity_score: Option<Decimal>,
    pub reason_json: Option<Value>,
    pub status: String,
    pub calculation_version: String,
    pub calculated_at: DateTime<Utc>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}
