use sqlx::MySqlPool;

use crate::{
    error::{AppError, AppResult},
    models::entity::ProductPlatform,
};

pub async fn list_by_platform(
    pool: &MySqlPool,
    platform: &str,
    offset: u64,
    limit: u64,
) -> AppResult<Vec<ProductPlatform>> {
    let limit = limit.clamp(1, 200);
    sqlx::query_as::<_, ProductPlatform>(
        r#"
        SELECT id, product_id, platform, platform_product_id, url, title,
               shop_id, shop_name, seller_id, status, first_seen_at, last_seen_at,
               created_at, updated_at
        FROM product_platforms
        WHERE platform = ?
        ORDER BY last_seen_at DESC, id DESC
        LIMIT ? OFFSET ?
        "#,
    )
    .bind(platform)
    .bind(limit)
    .bind(offset)
    .fetch_all(pool)
    .await
    .map_err(AppError::from)
}

pub async fn get(pool: &MySqlPool, id: u64) -> AppResult<ProductPlatform> {
    sqlx::query_as::<_, ProductPlatform>(
        r#"
        SELECT id, product_id, platform, platform_product_id, url, title,
               shop_id, shop_name, seller_id, status, first_seen_at, last_seen_at,
               created_at, updated_at
        FROM product_platforms
        WHERE id = ?
        "#,
    )
    .bind(id)
    .fetch_optional(pool)
    .await?
    .ok_or_else(|| AppError::NotFound("product platform not found".into()))
}
