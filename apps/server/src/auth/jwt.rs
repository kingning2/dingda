use chrono::{Duration, Utc};
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};

use crate::error::{AppError, AppResult};

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: u64,
    pub email: String,
    pub exp: i64,
    pub iat: i64,
}

pub struct IssuedToken {
    pub token: String,
    pub expires_at: chrono::DateTime<Utc>,
}

pub fn issue_token(
    user_id: u64,
    email: &str,
    secret: &str,
    expire_hours: u64,
) -> AppResult<IssuedToken> {
    let now = Utc::now();
    let expires_at = now + Duration::hours(expire_hours as i64);
    let claims = Claims {
        sub: user_id,
        email: email.to_string(),
        iat: now.timestamp(),
        exp: expires_at.timestamp(),
    };

    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )
    .map_err(|error| AppError::Other(error.into()))?;

    Ok(IssuedToken { token, expires_at })
}

pub fn decode_token(token: &str, secret: &str) -> AppResult<Claims> {
    decode::<Claims>(
        token,
        &DecodingKey::from_secret(secret.as_bytes()),
        &Validation::default(),
    )
    .map(|data| data.claims)
    .map_err(|_| AppError::Unauthorized("invalid or expired token".into()))
}
