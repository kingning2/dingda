use axum::{
    extract::{FromRequest, Request},
    Json,
};
use serde::de::DeserializeOwned;

use crate::error::AppError;

pub struct ApiJson<T>(pub T);

impl<T, S> FromRequest<S> for ApiJson<T>
where
    T: DeserializeOwned + Send,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        Json::<T>::from_request(req, state)
            .await
            .map(|Json(value)| ApiJson(value))
            .map_err(AppError::from_json_rejection)
    }
}
