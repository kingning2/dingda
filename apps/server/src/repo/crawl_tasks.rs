use chrono::Utc;
use sqlx::MySqlPool;

use crate::{
    error::{AppError, AppResult},
    models::entity::CrawlTask,
};

pub async fn create(
    pool: &MySqlPool,
    workspace_id: u64,
    client_ref: &str,
    platform: &str,
    discovery_task_id: Option<u64>,
) -> AppResult<CrawlTask> {
    let now = Utc::now();
    sqlx::query(
        r#"
        INSERT INTO crawl_tasks (
            workspace_id, discovery_task_id, client_ref, platform,
            task_type, status, started_at
        ) VALUES (?, ?, ?, ?, 'snapshot', 'pending', ?)
        "#,
    )
    .bind(workspace_id)
    .bind(discovery_task_id)
    .bind(client_ref)
    .bind(platform)
    .bind(now)
    .execute(pool)
    .await
    .map_err(|error| match error {
        sqlx::Error::Database(db_err) if db_err.code().as_deref() == Some("23000") => {
            AppError::Conflict("crawl task client_ref already exists".into())
        }
        other => AppError::from(other),
    })?;

    find_by_client_ref(pool, workspace_id, client_ref)
        .await?
        .ok_or_else(|| AppError::Other(anyhow::anyhow!("crawl task insert failed")))
}

pub async fn find_by_client_ref(
    pool: &MySqlPool,
    workspace_id: u64,
    client_ref: &str,
) -> AppResult<Option<CrawlTask>> {
    sqlx::query_as::<_, CrawlTask>(
        r#"
        SELECT id, workspace_id, discovery_task_id, client_ref, platform, task_type,
               target_url, status, total_count, success_count, failed_count,
               started_at, finished_at, error_message, client_id, crawler_version,
               data_version, created_at, updated_at
        FROM crawl_tasks
        WHERE workspace_id = ? AND client_ref = ?
        "#,
    )
    .bind(workspace_id)
    .bind(client_ref)
    .fetch_optional(pool)
    .await
    .map_err(AppError::from)
}

pub async fn get(pool: &MySqlPool, workspace_id: u64, task_id: u64) -> AppResult<CrawlTask> {
    sqlx::query_as::<_, CrawlTask>(
        r#"
        SELECT id, workspace_id, discovery_task_id, client_ref, platform, task_type,
               target_url, status, total_count, success_count, failed_count,
               started_at, finished_at, error_message, client_id, crawler_version,
               data_version, created_at, updated_at
        FROM crawl_tasks
        WHERE workspace_id = ? AND id = ?
        "#,
    )
    .bind(workspace_id)
    .bind(task_id)
    .fetch_optional(pool)
    .await?
    .ok_or_else(|| AppError::NotFound("crawl task not found".into()))
}

pub async fn resolve_for_batch(
    pool: &MySqlPool,
    workspace_id: u64,
    client_ref: &str,
    platform: &str,
) -> AppResult<CrawlTask> {
    if let Some(task) = find_by_client_ref(pool, workspace_id, client_ref).await? {
        return Ok(task);
    }

    let mut tx = pool.begin().await?;
    let now = Utc::now();
    sqlx::query(
        r#"
        INSERT INTO crawl_tasks (
            workspace_id, client_ref, platform, task_type, status, started_at
        ) VALUES (?, ?, ?, 'snapshot', 'running', ?)
        ON DUPLICATE KEY UPDATE
            status = IF(status = 'success', status, 'running'),
            updated_at = CURRENT_TIMESTAMP(6)
        "#,
    )
    .bind(workspace_id)
    .bind(client_ref)
    .bind(platform)
    .bind(now)
    .execute(&mut *tx)
    .await?;

    let task = find_by_client_ref_in_tx(&mut tx, workspace_id, client_ref)
        .await?
        .ok_or_else(|| AppError::Other(anyhow::anyhow!("crawl task upsert failed")))?;
    tx.commit().await?;
    Ok(task)
}

pub async fn bump_success(pool: &MySqlPool, task_id: u64, count: u32) -> AppResult<()> {
    sqlx::query(
        r#"
        UPDATE crawl_tasks
        SET success_count = success_count + ?,
            total_count = total_count + ?,
            status = 'running',
            updated_at = CURRENT_TIMESTAMP(6)
        WHERE id = ?
        "#,
    )
    .bind(count)
    .bind(count)
    .bind(task_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn bump_failed(pool: &MySqlPool, task_id: u64, count: u32) -> AppResult<()> {
    sqlx::query(
        r#"
        UPDATE crawl_tasks
        SET failed_count = failed_count + ?,
            total_count = total_count + ?,
            updated_at = CURRENT_TIMESTAMP(6)
        WHERE id = ?
        "#,
    )
    .bind(count)
    .bind(count)
    .bind(task_id)
    .execute(pool)
    .await?;
    Ok(())
}

async fn find_by_client_ref_in_tx(
    tx: &mut sqlx::Transaction<'_, sqlx::MySql>,
    workspace_id: u64,
    client_ref: &str,
) -> AppResult<Option<CrawlTask>> {
    sqlx::query_as::<_, CrawlTask>(
        r#"
        SELECT id, workspace_id, discovery_task_id, client_ref, platform, task_type,
               target_url, status, total_count, success_count, failed_count,
               started_at, finished_at, error_message, client_id, crawler_version,
               data_version, created_at, updated_at
        FROM crawl_tasks
        WHERE workspace_id = ? AND client_ref = ?
        "#,
    )
    .bind(workspace_id)
    .bind(client_ref)
    .fetch_optional(&mut **tx)
    .await
    .map_err(AppError::from)
}
