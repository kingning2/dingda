use sqlx::MySqlPool;

use crate::{
    error::{AppError, AppResult},
    models::entity::ProductSnapshotRow,
};

pub async fn list_by_platform(
    pool: &MySqlPool,
    product_platform_id: u64,
    offset: u64,
    limit: u64,
) -> AppResult<Vec<ProductSnapshotRow>> {
    let limit = limit.clamp(1, 200);
    sqlx::query_as::<_, ProductSnapshotRow>(
        r#"
        SELECT id, product_platform_id, crawl_task_id, captured_at, title, subtitle,
               description, brand, category, attributes_json, cover_url, snapshot_hash, created_at
        FROM product_snapshots
        WHERE product_platform_id = ?
        ORDER BY captured_at DESC, id DESC
        LIMIT ? OFFSET ?
        "#,
    )
    .bind(product_platform_id)
    .bind(limit)
    .bind(offset)
    .fetch_all(pool)
    .await
    .map_err(AppError::from)
}
