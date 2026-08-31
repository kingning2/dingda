pub mod jwt;
pub mod password;

use axum::{
    extract::{FromRef, FromRequestParts},
    http::{header::AUTHORIZATION, request::Parts},
};

use crate::{config::Config, error::AppError, state::AppState};

pub use jwt::issue_token;
pub use password::{hash_password, verify_password};

#[derive(Clone, Debug)]
pub struct AuthUser {
    pub user_id: u64,
    #[allow(dead_code)]
    pub email: String,
}

impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
    AppState: axum::extract::FromRef<S>,
    Config: axum::extract::FromRef<S>,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let config = Config::from_ref(state);

        let token = parts
            .headers
            .get(AUTHORIZATION)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.strip_prefix("Bearer "))
            .ok_or_else(|| AppError::Unauthorized("missing bearer token".into()))?;

        let claims = jwt::decode_token(token, &config.auth.jwt_secret)?;
        Ok(AuthUser {
            user_id: claims.sub,
            email: claims.email,
        })
    }
}
