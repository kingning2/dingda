use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};

use crate::{
    auth::{hash_password, issue_token, verify_password, AuthUser},
    error::{AppError, AppResult},
    extractors::ApiJson,
    models::dto::{AuthResponse, LoginInput, RegisterInput},
    models::entity::UserPublic,
    repo::users,
    repo::workspaces,
    state::AppState,
};

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/api/v1/auth/register", post(register))
        .route("/api/v1/auth/login", post(login))
        .route("/api/v1/auth/me", get(me))
}

async fn register(
    State(state): State<AppState>,
    ApiJson(input): ApiJson<RegisterInput>,
) -> AppResult<(StatusCode, Json<AuthResponse>)> {
    validate_credentials(&input.email, &input.password)?;

    let password_hash = hash_password(&input.password)?;
    let (user, workspace_id) = users::create_user_with_workspace(
        &state.pool,
        &input.email,
        input.name.as_deref(),
        &password_hash,
    )
    .await?;

    let issued = issue_token(
        user.id,
        &user.email,
        &state.config.auth.jwt_secret,
        state.config.auth.jwt_expire_hours,
    )?;

    Ok((
        StatusCode::CREATED,
        Json(AuthResponse {
            token: issued.token,
            expires_at: issued.expires_at,
            user: user.to_public(),
            workspace_id,
        }),
    ))
}

async fn login(
    State(state): State<AppState>,
    ApiJson(input): ApiJson<LoginInput>,
) -> AppResult<Json<AuthResponse>> {
    validate_credentials(&input.email, &input.password)?;

    let user = users::find_user_by_email(&state.pool, &input.email)
        .await?
        .ok_or_else(|| AppError::Unauthorized("invalid email or password".into()))?;

    if !verify_password(&input.password, &user.password_hash)? {
        return Err(AppError::Unauthorized("invalid email or password".into()));
    }

    let workspace_id = workspaces::default_workspace_id(&state.pool, user.id).await?;
    let issued = issue_token(
        user.id,
        &user.email,
        &state.config.auth.jwt_secret,
        state.config.auth.jwt_expire_hours,
    )?;

    Ok(Json(AuthResponse {
        token: issued.token,
        expires_at: issued.expires_at,
        user: user.to_public(),
        workspace_id,
    }))
}

async fn me(State(state): State<AppState>, auth: AuthUser) -> AppResult<Json<UserPublic>> {
    let user = users::find_user_by_id(&state.pool, auth.user_id)
        .await?
        .ok_or_else(|| AppError::Unauthorized("user not found".into()))?;

    Ok(Json(user.to_public()))
}

fn validate_credentials(email: &str, password: &str) -> AppResult<()> {
    let email = email.trim();
    if !email.contains('@') || email.len() > 255 {
        return Err(AppError::BadRequest("invalid email".into()));
    }
    if password.len() < 8 || password.len() > 128 {
        return Err(AppError::BadRequest(
            "password must be 8-128 characters".into(),
        ));
    }
    Ok(())
}
