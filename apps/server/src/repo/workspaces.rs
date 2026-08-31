use sqlx::MySqlPool;

use crate::error::{AppError, AppResult};

pub async fn ensure_member(pool: &MySqlPool, workspace_id: u64, user_id: u64) -> AppResult<()> {
    let exists: Option<i64> = sqlx::query_scalar(
        r#"
        SELECT 1 FROM workspace_members
        WHERE workspace_id = ? AND user_id = ?
        LIMIT 1
        "#,
    )
    .bind(workspace_id)
    .bind(user_id)
    .fetch_optional(pool)
    .await?;

    if exists.is_some() {
        Ok(())
    } else {
        Err(AppError::Unauthorized("workspace access denied".into()))
    }
}

pub async fn default_workspace_id(pool: &MySqlPool, user_id: u64) -> AppResult<u64> {
    let workspace_id: Option<u64> = sqlx::query_scalar(
        r#"
        SELECT w.id
        FROM workspaces w
        INNER JOIN workspace_members wm ON wm.workspace_id = w.id
        WHERE wm.user_id = ?
        ORDER BY w.id ASC
        LIMIT 1
        "#,
    )
    .bind(user_id)
    .fetch_optional(pool)
    .await?;

    workspace_id.ok_or_else(|| AppError::NotFound("workspace not found".into()))
}
