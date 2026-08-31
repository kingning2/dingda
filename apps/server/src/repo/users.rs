use sqlx::{MySql, MySqlPool, Transaction};

use crate::{
    error::{AppError, AppResult},
    models::entity::User,
};

pub async fn create_user_with_workspace(
    pool: &MySqlPool,
    email: &str,
    name: Option<&str>,
    password_hash: &str,
) -> AppResult<(User, u64)> {
    let mut tx = pool.begin().await?;

    let user = insert_user(&mut tx, email, name, password_hash).await?;
    let workspace_id = insert_workspace(
        &mut tx,
        &format!("{}的工作区", name.unwrap_or(email)),
        user.id,
    )
    .await?;
    insert_workspace_member(&mut tx, workspace_id, user.id, "owner").await?;

    tx.commit().await?;
    Ok((user, workspace_id))
}

pub async fn find_user_by_email(pool: &MySqlPool, email: &str) -> AppResult<Option<User>> {
    let user = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, avatar, status, password_hash, created_at, updated_at
        FROM users WHERE email = ?
        "#,
    )
    .bind(email)
    .fetch_optional(pool)
    .await?;
    Ok(user)
}

pub async fn find_user_by_id(pool: &MySqlPool, id: u64) -> AppResult<Option<User>> {
    let user = sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, avatar, status, password_hash, created_at, updated_at
        FROM users WHERE id = ?
        "#,
    )
    .bind(id)
    .fetch_optional(pool)
    .await?;
    Ok(user)
}

async fn insert_user(
    tx: &mut Transaction<'_, MySql>,
    email: &str,
    name: Option<&str>,
    password_hash: &str,
) -> AppResult<User> {
    let result = sqlx::query(
        r#"
        INSERT INTO users (email, name, password_hash, status)
        VALUES (?, ?, ?, 'active')
        "#,
    )
    .bind(email)
    .bind(name)
    .bind(password_hash)
    .execute(&mut **tx)
    .await;

    match result {
        Ok(_) => find_user_by_email_in_tx(tx, email).await,
        Err(sqlx::Error::Database(error)) if error.code().as_deref() == Some("23000") => {
            Err(AppError::Conflict("email already exists".into()))
        }
        Err(error) => Err(AppError::from(error)),
    }
}

async fn find_user_by_email_in_tx(tx: &mut Transaction<'_, MySql>, email: &str) -> AppResult<User> {
    sqlx::query_as::<_, User>(
        r#"
        SELECT id, email, name, avatar, status, password_hash, created_at, updated_at
        FROM users WHERE email = ?
        "#,
    )
    .bind(email)
    .fetch_one(&mut **tx)
    .await
    .map_err(AppError::from)
}

async fn insert_workspace(
    tx: &mut Transaction<'_, MySql>,
    name: &str,
    owner_id: u64,
) -> AppResult<u64> {
    let result = sqlx::query(
        r#"
        INSERT INTO workspaces (name, owner_id, status)
        VALUES (?, ?, 'active')
        "#,
    )
    .bind(name)
    .bind(owner_id)
    .execute(&mut **tx)
    .await?;

    Ok(result.last_insert_id())
}

async fn insert_workspace_member(
    tx: &mut Transaction<'_, MySql>,
    workspace_id: u64,
    user_id: u64,
    role: &str,
) -> AppResult<()> {
    sqlx::query(
        r#"
        INSERT INTO workspace_members (workspace_id, user_id, role)
        VALUES (?, ?, ?)
        "#,
    )
    .bind(workspace_id)
    .bind(user_id)
    .bind(role)
    .execute(&mut **tx)
    .await?;
    Ok(())
}
