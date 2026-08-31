use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::Value;
use sqlx::FromRow;

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct DiscoveryTask {
    pub id: u64,
    pub workspace_id: u64,
    pub keyword: Option<String>,
    pub platforms: Option<Value>,
    pub status: String,
    pub started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct CrawlTask {
    pub id: u64,
    pub workspace_id: u64,
    pub discovery_task_id: Option<u64>,
    pub client_ref: Option<String>,
    pub platform: String,
    pub task_type: String,
    pub target_url: Option<String>,
    pub status: String,
    pub total_count: u32,
    pub success_count: u32,
    pub failed_count: u32,
    pub started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub client_id: Option<String>,
    pub crawler_version: Option<String>,
    pub data_version: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct ProductWatch {
    pub id: u64,
    pub workspace_id: u64,
    pub product_id: u64,
    pub product_platform_id: u64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}
