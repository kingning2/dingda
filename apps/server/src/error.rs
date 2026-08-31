use axum::{
    extract::rejection::JsonRejection,
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;
use thiserror::Error;

use crate::middleware::context::current_request_id;

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ErrorCode {
    BadRequest,
    Unauthorized,
    NotFound,
    Conflict,
    InternalError,
}

#[derive(Debug, Error)]
pub enum AppError {
    #[error("{0}")]
    BadRequest(String),
    #[error("{0}")]
    NotFound(String),
    #[error("{0}")]
    Conflict(String),
    #[error("{0}")]
    Unauthorized(String),
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

impl AppError {
    pub fn from_json_rejection(rejection: JsonRejection) -> Self {
        let message = match rejection {
            JsonRejection::JsonDataError(error) => {
                format!("invalid request body: {}", error)
            }
            JsonRejection::JsonSyntaxError(error) => format!("invalid json: {}", error),
            JsonRejection::MissingJsonContentType(_) => {
                "missing application/json content-type".into()
            }
            JsonRejection::BytesRejection(_) => "failed to read request body".into(),
            _ => "invalid request body".into(),
        };
        AppError::BadRequest(message)
    }

    fn code(&self) -> ErrorCode {
        match self {
            AppError::BadRequest(_) => ErrorCode::BadRequest,
            AppError::Unauthorized(_) => ErrorCode::Unauthorized,
            AppError::NotFound(_) => ErrorCode::NotFound,
            AppError::Conflict(_) => ErrorCode::Conflict,
            AppError::Database(_) | AppError::Other(_) => ErrorCode::InternalError,
        }
    }

    fn status(&self) -> StatusCode {
        match self.code() {
            ErrorCode::BadRequest => StatusCode::BAD_REQUEST,
            ErrorCode::Unauthorized => StatusCode::UNAUTHORIZED,
            ErrorCode::NotFound => StatusCode::NOT_FOUND,
            ErrorCode::Conflict => StatusCode::CONFLICT,
            ErrorCode::InternalError => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    fn client_message(&self) -> String {
        match self {
            AppError::BadRequest(message)
            | AppError::NotFound(message)
            | AppError::Conflict(message)
            | AppError::Unauthorized(message) => message.clone(),
            AppError::Database(error) => {
                tracing::error!(error = %error, "database error");
                "internal server error".into()
            }
            AppError::Other(error) => {
                tracing::error!(error = %error, "unhandled error");
                "internal server error".into()
            }
        }
    }
}

#[derive(Serialize)]
struct ApiErrorBody {
    error: ApiErrorDetail,
}

#[derive(Serialize)]
struct ApiErrorDetail {
    code: ErrorCode,
    message: String,
    request_id: String,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = self.status();
        let body = ApiErrorBody {
            error: ApiErrorDetail {
                code: self.code(),
                message: self.client_message(),
                request_id: current_request_id(),
            },
        };

        (status, Json(body)).into_response()
    }
}

pub type AppResult<T> = Result<T, AppError>;

impl From<serde_json::Error> for AppError {
    fn from(value: serde_json::Error) -> Self {
        AppError::Other(value.into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::StatusCode;

    #[test]
    fn error_maps_to_http_status() {
        assert_eq!(
            AppError::BadRequest("x".into()).into_response().status(),
            StatusCode::BAD_REQUEST
        );
        assert_eq!(
            AppError::Unauthorized("x".into()).into_response().status(),
            StatusCode::UNAUTHORIZED
        );
        assert_eq!(
            AppError::NotFound("x".into()).into_response().status(),
            StatusCode::NOT_FOUND
        );
        assert_eq!(
            AppError::Conflict("x".into()).into_response().status(),
            StatusCode::CONFLICT
        );
    }
}
