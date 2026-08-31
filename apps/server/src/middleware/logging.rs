use std::time::Instant;

use axum::{body::Body, http::Request, middleware::Next, response::Response};

use super::context::current_request_id;

pub async fn log_requests(request: Request<Body>, next: Next) -> Response {
    let method = request.method().clone();
    let path = request.uri().path().to_string();
    let query = request
        .uri()
        .query()
        .map(|value| format!("?{value}"))
        .unwrap_or_default();
    let request_id = current_request_id();
    let started = Instant::now();

    let response = next.run(request).await;

    let status = response.status().as_u16();
    let duration_ms = started.elapsed().as_millis();

    if status >= 500 {
        tracing::error!(
            request_id = %request_id,
            method = %method,
            path = %format!("{path}{query}"),
            status,
            duration_ms,
            "http request failed"
        );
    } else if status >= 400 {
        tracing::warn!(
            request_id = %request_id,
            method = %method,
            path = %format!("{path}{query}"),
            status,
            duration_ms,
            "http request rejected"
        );
    } else {
        tracing::info!(
            request_id = %request_id,
            method = %method,
            path = %format!("{path}{query}"),
            status,
            duration_ms,
            "http request"
        );
    }

    response
}
