use axum::{
    extract::{Path, Query, State},
    routing::get,
    Json, Router,
};

use crate::{
    auth::AuthUser,
    error::AppResult,
    models::dto::{PlatformListQuery, SnapshotListQuery},
    repo::{product_platforms, snapshot_query},
    state::AppState,
};

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/api/v1/product-platforms", get(list_platforms))
        .route("/api/v1/product-platforms/{id}", get(get_platform))
        .route("/api/v1/snapshots", get(list_snapshots))
}

async fn list_platforms(
    State(state): State<AppState>,
    _auth: AuthUser,
    Query(query): Query<PlatformListQuery>,
) -> AppResult<Json<Vec<crate::models::entity::ProductPlatform>>> {
    Ok(Json(
        product_platforms::list_by_platform(
            &state.pool,
            &query.platform,
            query.offset.unwrap_or(0),
            query.limit.unwrap_or(50),
        )
        .await?,
    ))
}

async fn get_platform(
    State(state): State<AppState>,
    _auth: AuthUser,
    Path(id): Path<u64>,
) -> AppResult<Json<crate::models::entity::ProductPlatform>> {
    Ok(Json(product_platforms::get(&state.pool, id).await?))
}

async fn list_snapshots(
    State(state): State<AppState>,
    _auth: AuthUser,
    Query(query): Query<SnapshotListQuery>,
) -> AppResult<Json<Vec<crate::models::entity::ProductSnapshotRow>>> {
    Ok(Json(
        snapshot_query::list_by_platform(
            &state.pool,
            query.product_platform_id,
            query.offset.unwrap_or(0),
            query.limit.unwrap_or(50),
        )
        .await?,
    ))
}
