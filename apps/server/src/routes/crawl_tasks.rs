use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};

use crate::{
    auth::AuthUser,
    error::AppResult,
    extractors::ApiJson,
    models::{dto::CreateCrawlTaskInput, entity::CrawlTask},
    repo::{crawl_tasks, workspaces},
    state::AppState,
};

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/api/v1/crawl-tasks", post(create).get(list_placeholder))
        .route("/api/v1/crawl-tasks/{id}", get(get_one))
}

async fn create(
    State(state): State<AppState>,
    auth: AuthUser,
    ApiJson(input): ApiJson<CreateCrawlTaskInput>,
) -> AppResult<(StatusCode, Json<CrawlTask>)> {
    let workspace_id = match input.workspace_id {
        Some(id) => id,
        None => workspaces::default_workspace_id(&state.pool, auth.user_id).await?,
    };
    workspaces::ensure_member(&state.pool, workspace_id, auth.user_id).await?;

    let task = crawl_tasks::create(
        &state.pool,
        workspace_id,
        &input.client_ref,
        &input.platform,
        input.discovery_task_id,
    )
    .await?;

    Ok((StatusCode::CREATED, Json(task)))
}

async fn get_one(
    State(state): State<AppState>,
    auth: AuthUser,
    Path(id): Path<u64>,
) -> AppResult<Json<CrawlTask>> {
    let workspace_id = workspaces::default_workspace_id(&state.pool, auth.user_id).await?;
    workspaces::ensure_member(&state.pool, workspace_id, auth.user_id).await?;
    Ok(Json(crawl_tasks::get(&state.pool, workspace_id, id).await?))
}

async fn list_placeholder() -> &'static str {
    "use GET /api/v1/crawl-tasks/{id}"
}
