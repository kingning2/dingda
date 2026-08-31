mod auth;
mod catalog;
mod crawl_tasks;
mod snapshots;

use axum::Router;

use crate::state::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .merge(auth::router())
        .merge(crawl_tasks::router())
        .merge(snapshots::router())
        .merge(catalog::router())
}
