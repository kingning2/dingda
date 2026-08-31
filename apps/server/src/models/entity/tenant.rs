use chrono::{DateTime, Utc};
use serde::Serialize;
use sqlx::FromRow;

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct User {
    pub id: u64,
    pub email: String,
    pub name: Option<String>,
    pub avatar: Option<String>,
    pub status: String,
    #[serde(skip_serializing)]
    pub password_hash: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl User {
    pub fn to_public(self) -> UserPublic {
        UserPublic {
            id: self.id,
            email: self.email,
            name: self.name,
            avatar: self.avatar,
            status: self.status,
            created_at: self.created_at,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct UserPublic {
    pub id: u64,
    pub email: String,
    pub name: Option<String>,
    pub avatar: Option<String>,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct Workspace {
    pub id: u64,
    pub name: String,
    pub owner_id: u64,
    pub status: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, FromRow)]
pub struct WorkspaceMember {
    pub id: u64,
    pub workspace_id: u64,
    pub user_id: u64,
    pub role: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}
