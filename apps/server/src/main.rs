mod auth;
mod config;
mod engine;
mod error;
mod extractors;
mod middleware;
mod models;
mod pool;
mod repo;
mod routes;
mod services;
mod state;
mod system;

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{extract::DefaultBodyLimit, extract::State, routing::get, Json, Router};
use config::Config;
use serde::Serialize;
use state::AppState;
use tower_http::cors::CorsLayer;
use tracing_subscriber::EnvFilter;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    let config = Config::from_env()?;
    let workers = config.tokio_workers();

    tracing::info!(
        cpus = config.system.cpus,
        memory_mb = config.system.memory_mb(),
        tokio_workers = workers,
        "runtime autotune"
    );

    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(workers)
        .enable_all()
        .build()?;

    runtime.block_on(async_main(config))
}

async fn async_main(config: Config) -> anyhow::Result<()> {
    let config = Arc::new(config);
    let pool = pool::create_pool(&config).await?;

    sqlx::migrate!("./migrations").run(&pool).await?;

    let app_state = AppState {
        pool: pool.clone(),
        config: config.clone(),
    };

    let app = middleware::apply(
        Router::new()
            .route("/health", get(health))
            .merge(routes::router())
            .layer(DefaultBodyLimit::max(config.http_max_body_bytes))
            .layer(CorsLayer::permissive()),
    )
    .with_state(app_state);

    let addr: SocketAddr = format!("{}:{}", config.host, config.port).parse()?;
    tracing::info!(
        %addr,
        cpus = config.system.cpus,
        memory_mb = config.system.memory_mb(),
        tokio_workers = config.tokio_workers(),
        http_max_body_mb = config.http_max_body_bytes / (1024 * 1024),
        db_pool_max = config.pool.max_connections,
        db_pool_min = config.pool.min_connections,
        bulk_batch_size = config.bulk.batch_size,
        bulk_max_items = config.bulk.max_items,
        "server listening"
    );

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    Ok(())
}

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    system: system::ResourceProfile,
    db: HealthDb,
}

#[derive(Serialize)]
struct HealthDb {
    pool_size: u32,
    pool_idle: u32,
    pool_max_connections: u32,
}

async fn health(State(state): State<AppState>) -> Json<HealthResponse> {
    let stats = pool::pool_stats(&state.pool);
    Json(HealthResponse {
        status: "ok",
        system: state.config.system,
        db: HealthDb {
            pool_size: stats.size,
            pool_idle: stats.idle,
            pool_max_connections: state.config.pool.max_connections,
        },
    })
}

async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = ctrl_c => {},
        () = terminate => {},
    }

    tracing::info!("shutdown signal received, draining connections");
}
