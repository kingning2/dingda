use std::env;
use std::time::Duration;

use crate::system::ResourceProfile;

#[derive(Clone, Debug)]
pub struct Config {
    pub database_url: String,
    pub host: String,
    pub port: u16,
    pub pool: PoolConfig,
    pub bulk: BulkConfig,
    pub http_max_body_bytes: usize,
    pub auth: AuthConfig,
    pub system: ResourceProfile,
}

#[derive(Clone, Debug)]
pub struct AuthConfig {
    pub jwt_secret: String,
    pub jwt_expire_hours: u64,
}

#[derive(Clone, Debug)]
pub struct PoolConfig {
    pub max_connections: u32,
    pub min_connections: u32,
    pub acquire_timeout: Duration,
    pub idle_timeout: Duration,
    pub max_lifetime: Duration,
}

#[derive(Clone, Debug)]
pub struct BulkConfig {
    pub batch_size: usize,
    pub max_items: usize,
}

impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        let system = ResourceProfile::detect();

        let pool = PoolConfig {
            max_connections: env_u32_or(
                "DB_POOL_MAX_CONNECTIONS",
                system.db_pool_max_connections(),
            ),
            min_connections: env_u32_or(
                "DB_POOL_MIN_CONNECTIONS",
                system.db_pool_min_connections(),
            ),
            acquire_timeout: Duration::from_secs(env_u64("DB_POOL_ACQUIRE_TIMEOUT_SECS", 15)),
            idle_timeout: Duration::from_secs(env_u64("DB_POOL_IDLE_TIMEOUT_SECS", 300)),
            max_lifetime: Duration::from_secs(env_u64("DB_POOL_MAX_LIFETIME_SECS", 900)),
        }
        .normalize();

        Ok(Self {
            database_url: env::var("DATABASE_URL").unwrap_or_else(|_| {
                "mysql://dingda:dingda@127.0.0.1:3306/dingda_products".to_string()
            }),
            host: env::var("API_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
            port: env_u16("API_PORT", 8080),
            pool,
            bulk: BulkConfig {
                batch_size: env_usize_or("DB_BULK_BATCH_SIZE", system.bulk_batch_size()),
                max_items: env_usize_or("DB_BULK_MAX_ITEMS", system.bulk_max_items()),
            },
            http_max_body_bytes: env_usize_or("HTTP_MAX_BODY_MB", system.http_max_body_mb())
                .saturating_mul(1024 * 1024),
            auth: AuthConfig {
                jwt_secret: env::var("JWT_SECRET")
                    .unwrap_or_else(|_| "dev-only-change-me-in-production".to_string()),
                jwt_expire_hours: env_u64("JWT_EXPIRE_HOURS", 168),
            },
            system,
        })
    }

    pub fn tokio_workers(&self) -> usize {
        env_usize("TOKIO_WORKER_THREADS", self.system.tokio_workers())
    }
}

impl PoolConfig {
    fn normalize(mut self) -> Self {
        self.max_connections = self.max_connections.clamp(1, 32);
        self.min_connections = self.min_connections.clamp(0, self.max_connections);
        self
    }
}

fn env_u16(key: &str, default: u16) -> u16 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_u32_or(key: &str, default: u32) -> u32 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_u64(key: &str, default: u64) -> u64 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_usize(key: &str, default: usize) -> usize {
    env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_usize_or(key: &str, default: usize) -> usize {
    env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}
