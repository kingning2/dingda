//! Sidecar: POST /v1/channel/xianyu/user_profile

use serde::{Deserialize, Serialize};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserProfileRequest {
    pub cookie: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UserProfileDto {
    #[serde(default)]
    pub display_name: String,
    #[serde(default)]
    pub avatar_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserProfileResponse {
    pub ok: bool,
    #[serde(default)]
    pub profile: Option<UserProfileDto>,
    #[serde(default)]
    pub cookie: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn call(
    client: &SidecarClient,
    request: UserProfileRequest,
) -> Result<UserProfileResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/user_profile", &request)
        .await
}
