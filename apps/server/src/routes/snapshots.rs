use axum::{extract::State, routing::post, Json, Router};

use crate::{
    auth::AuthUser, error::AppResult, extractors::ApiJson, models::dto::SnapshotBatchRequest,
    services::snapshot_ingest, state::AppState,
};

pub fn router() -> Router<AppState> {
    Router::new().route("/api/v1/snapshots/batch", post(batch_upload))
}

async fn batch_upload(
    State(state): State<AppState>,
    auth: AuthUser,
    ApiJson(request): ApiJson<SnapshotBatchRequest>,
) -> AppResult<Json<crate::models::dto::SnapshotBatchResponse>> {
    if request.snapshots.len() > state.config.bulk.max_items {
        return Err(crate::error::AppError::BadRequest(format!(
            "snapshots exceed limit: {} > {}",
            request.snapshots.len(),
            state.config.bulk.max_items
        )));
    }

    Ok(Json(
        snapshot_ingest::ingest_batch(&state.pool, auth.user_id, request).await?,
    ))
}
