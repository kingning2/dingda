use sqlx::mysql::MySqlPoolOptions;
use sqlx::MySqlPool;
use tracing::info;

use crate::config::Config;

pub async fn create_pool(config: &Config) -> anyhow::Result<MySqlPool> {
    let pool_config = &config.pool;

    let pool = MySqlPoolOptions::new()
        .max_connections(pool_config.max_connections)
        .min_connections(pool_config.min_connections)
        .acquire_timeout(pool_config.acquire_timeout)
        .idle_timeout(pool_config.idle_timeout)
        .max_lifetime(pool_config.max_lifetime)
        .test_before_acquire(true)
        .connect(&config.database_url)
        .await?;

    info!(
        max_connections = pool_config.max_connections,
        min_connections = pool_config.min_connections,
        acquire_timeout_secs = pool_config.acquire_timeout.as_secs(),
        idle_timeout_secs = pool_config.idle_timeout.as_secs(),
        max_lifetime_secs = pool_config.max_lifetime.as_secs(),
        "mysql pool ready"
    );

    Ok(pool)
}

pub fn pool_stats(pool: &MySqlPool) -> PoolStats {
    PoolStats {
        size: pool.size(),
        idle: pool.num_idle() as u32,
    }
}

#[derive(Debug, serde::Serialize)]
pub struct PoolStats {
    pub size: u32,
    pub idle: u32,
}
