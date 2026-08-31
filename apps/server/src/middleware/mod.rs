pub mod context;
pub mod logging;

use axum::{middleware, Router};

use crate::error::AppError;

use self::context::set_request_context;
use self::logging::log_requests;

/// Outermost layer runs first on inbound requests.
pub fn apply<S>(router: Router<S>) -> Router<S>
where
    S: Clone + Send + Sync + 'static,
{
    router
        .fallback(not_found)
        .method_not_allowed_fallback(method_not_allowed)
        .layer(middleware::from_fn(log_requests))
        .layer(middleware::from_fn(set_request_context))
}

async fn not_found() -> AppError {
    AppError::NotFound("route not found".into())
}

async fn method_not_allowed() -> AppError {
    AppError::BadRequest("method not allowed".into())
}
