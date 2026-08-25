//! 两站共用启动 — 打开业务库、注册账号 CRUD / 扫码 Handle。
//!
//! 无条件调用（`lib.rs` setup 第一步）：账号 CRUD 与扫码登录只注册一次，
//! 不再按 `xianyu` / `ali1688` 分支重复注册。扫码后置逻辑（闲鱼建渠道 WS）由
//! 闲鱼 bootstrap 通过 [`crate::cmd::AccountQrHandle::post_login`] 写入。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

use crate::cmd::AccountHandle;
use crate::cmd::AccountQrHandle;
use crate::contracts::DingDaResult;
use crate::core::store::{InMemoryAccountStore, SqliteBusinessDb};
use std::path::{Path, PathBuf};
use std::sync::{Arc, RwLock};
use tauri::Manager;

/// 打开业务 SQLite 并注册两站共用的账号 / 扫码 Handle。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-22
///
/// # 参数
///
/// * `app` — Tauri 应用句柄
/// * `config_dir` — 应用配置目录
///
/// # 返回值
///
/// 成功返回共享业务库；打开或迁移失败返回错误文案。
pub fn register_business(
    app: &tauri::AppHandle,
    config_dir: &Path,
) -> DingDaResult<Arc<SqliteBusinessDb>> {
    let business_dir = config_dir.join("business");
    std::fs::create_dir_all(&business_dir).map_err(|error| error.to_string())?;
    let db = SqliteBusinessDb::open(
        &business_dir.join("business.db"),
        &PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations"),
    )
    .map_err(|error| error.to_string())?;
    let business_db = Arc::new(db.clone());
    app.manage(business_db.clone());

    let accounts = Arc::new(InMemoryAccountStore::new(db));
    app.manage(AccountHandle {
        store: accounts.clone(),
    });
    // 扫码后置逻辑初始为 `None`；闲鱼 bootstrap 启动时写入。
    app.manage(AccountQrHandle {
        store: accounts,
        post_login: RwLock::new(None),
    });

    Ok(business_db)
}
