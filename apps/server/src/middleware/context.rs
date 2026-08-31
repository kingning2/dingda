use std::cell::RefCell;

use axum::{
    body::Body,
    http::{HeaderValue, Request},
    middleware::Next,
    response::Response,
};
use tokio::task_local;

task_local! {
    static REQUEST_ID: RefCell<String>;
}

#[derive(Clone, Debug)]
pub struct RequestId(pub String);

pub fn current_request_id() -> String {
    REQUEST_ID
        .try_with(|id| id.borrow().clone())
        .unwrap_or_else(|_| "unknown".to_string())
}

pub async fn set_request_context(mut request: Request<Body>, next: Next) -> Response {
    let request_id = request
        .headers()
        .get("x-request-id")
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());

    request
        .extensions_mut()
        .insert(RequestId(request_id.clone()));

    REQUEST_ID
        .scope(RefCell::new(request_id.clone()), async move {
            let mut response = next.run(request).await;
            if let Ok(header) = HeaderValue::from_str(&request_id) {
                response.headers_mut().insert("x-request-id", header);
            }
            response
        })
        .await
}
