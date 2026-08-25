//! 闲鱼业务 SQLite 基础设施 — JSON 记录存取。
//!
//! 所有业务 Store 通过本模块持久化到 `business_records(domain, record_id, owner_id, payload)`。
//! 表结构由 `apps/desktop/src-tauri/migrations/` 中的迁移文件建立。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;

use diesel::sql_types::{BigInt, Text};
use diesel::{QueryableByName, RunQueryDsl, SqliteConnection};

/// 业务数据库错误。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Debug, thiserror::Error)]
pub enum BusinessStoreError {
    #[error("db error: {0}")]
    Db(String),
    #[error("json error: {0}")]
    Json(String),
    #[allow(dead_code)]
    #[error("lock poisoned: {0}")]
    Poisoned(String),
}

impl From<BusinessStoreError> for crate::contracts::DingDaError {
    fn from(err: BusinessStoreError) -> Self {
        crate::contracts::DingDaError::store(err.to_string())
    }
}

#[derive(QueryableByName)]
struct PayloadRow {
    #[diesel(sql_type = Text)]
    payload: String,
}

#[derive(QueryableByName)]
struct RecordIdRow {
    #[diesel(sql_type = Text)]
    record_id: String,
}

type MutexGuard<'a> = std::sync::MutexGuard<'a, SqliteConnection>;

/// SQLite 业务数据库（单连接 + 迁移）。
///
/// 采用通用 JSON 记录表 `business_records(domain, record_id, owner_id, payload)`
/// 存储所有业务实体，避免为每种实体单独建表。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct SqliteBusinessDb {
    db: Arc<crate::core::storage::sqlite::SqliteDb>,
}

impl SqliteBusinessDb {
    /// 打开数据库并运行迁移。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `db_path` — SQLite 文件路径
    /// - `migrations_dir` — 迁移 SQL 目录
    ///
    /// # 返回值
    /// 打开并迁移后的数据库，或错误。
    pub fn open(db_path: &Path, migrations_dir: &Path) -> Result<Self, BusinessStoreError> {
        let db = crate::core::storage::sqlite::SqliteDb::open(db_path)
            .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        db.migrate(migrations_dir)
            .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        Ok(Self { db: Arc::new(db) })
    }

    fn conn(&self) -> Result<MutexGuard<'_>, BusinessStoreError> {
        self.db
            .connection()
            .map_err(|error| BusinessStoreError::Db(error.to_string()))
    }

    /// 访问底层连接（跨 owner 全局查询用）。
    pub fn connection(&self) -> Result<MutexGuard<'_>, BusinessStoreError> {
        self.conn()
    }

    /// 读取某域全部记录并反序列化。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `domain` — 业务域名（如 `"account"`）
    /// - `owner_id` — 归属用户 id
    ///
    /// # 返回值
    /// 反序列化后的记录列表，或错误。
    pub fn scan<T: for<'de> Deserialize<'de>>(
        &self,
        domain: &str,
        owner_id: i64,
    ) -> Result<Vec<T>, BusinessStoreError> {
        let mut conn = self.conn()?;
        let rows: Vec<PayloadRow> = diesel::sql_query(
            "SELECT payload FROM business_records WHERE domain = ? AND owner_id = ?",
        )
        .bind::<Text, _>(domain)
        .bind::<BigInt, _>(&owner_id)
        .load(&mut *conn)
        .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        rows.into_iter()
            .map(|row| {
                serde_json::from_str(&row.payload)
                    .map_err(|error| BusinessStoreError::Json(error.to_string()))
            })
            .collect()
    }

    /// 按主键读取单条记录并反序列化。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `domain` — 业务域名
    /// - `record_id` — 记录主键
    /// - `owner_id` — 归属用户 id
    ///
    /// # 返回值
    /// `Some(T)` 若存在，`None` 若不存在，或错误。
    pub fn get<T: for<'de> Deserialize<'de>>(
        &self,
        domain: &str,
        record_id: &str,
        owner_id: i64,
    ) -> Result<Option<T>, BusinessStoreError> {
        let mut conn = self.conn()?;
        let rows: Vec<PayloadRow> = diesel::sql_query(
            "SELECT payload FROM business_records WHERE domain = ? AND record_id = ? AND owner_id = ?",
        )
        .bind::<Text, _>(domain)
        .bind::<Text, _>(record_id)
        .bind::<BigInt, _>(&owner_id)
        .load(&mut *conn)
        .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        rows.into_iter().next().map_or(Ok(None), |row| {
            serde_json::from_str(&row.payload)
                .map(Some)
                .map_err(|error| BusinessStoreError::Json(error.to_string()))
        })
    }

    /// Upsert 单条记录（JSON 序列化）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `domain` — 业务域名
    /// - `record_id` — 记录主键
    /// - `owner_id` — 归属用户 id
    /// - `value` — 待存储值
    ///
    /// # 返回值
    /// 成功或错误。
    pub fn put<T: Serialize>(
        &self,
        domain: &str,
        record_id: &str,
        owner_id: i64,
        value: &T,
    ) -> Result<(), BusinessStoreError> {
        let payload = serde_json::to_string(value)
            .map_err(|error| BusinessStoreError::Json(error.to_string()))?;
        let mut conn = self.conn()?;
        diesel::sql_query(
            "INSERT INTO business_records (domain, record_id, owner_id, payload) \
             VALUES (?, ?, ?, ?) \
             ON CONFLICT(domain, record_id) DO UPDATE SET owner_id=excluded.owner_id, payload=excluded.payload",
        )
        .bind::<Text, _>(domain)
        .bind::<Text, _>(record_id)
        .bind::<BigInt, _>(&owner_id)
        .bind::<Text, _>(&payload)
        .execute(&mut *conn)
        .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        Ok(())
    }

    /// 按主键删除记录。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `domain` — 业务域名
    /// - `record_id` — 记录主键
    /// - `owner_id` — 归属用户 id
    ///
    /// # 返回值
    /// 成功或错误。
    pub fn delete(
        &self,
        domain: &str,
        record_id: &str,
        owner_id: i64,
    ) -> Result<(), BusinessStoreError> {
        let mut conn = self.conn()?;
        diesel::sql_query(
            "DELETE FROM business_records WHERE domain = ? AND record_id = ? AND owner_id = ?",
        )
        .bind::<Text, _>(domain)
        .bind::<Text, _>(record_id)
        .bind::<BigInt, _>(&owner_id)
        .execute(&mut *conn)
        .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        Ok(())
    }

    /// 生成域内自增 id（当前最大整数 id + 1）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `domain` — 业务域名
    /// - `owner_id` — 归属用户 id
    ///
    /// # 返回值
    /// 新 id（正整数）。
    pub fn next_id(&self, domain: &str, owner_id: i64) -> Result<i64, BusinessStoreError> {
        let mut conn = self.conn()?;
        let rows: Vec<RecordIdRow> = diesel::sql_query(
            "SELECT record_id FROM business_records WHERE domain = ? AND owner_id = ?",
        )
        .bind::<Text, _>(domain)
        .bind::<BigInt, _>(&owner_id)
        .load(&mut *conn)
        .map_err(|error| BusinessStoreError::Db(error.to_string()))?;
        let max_id = rows
            .into_iter()
            .filter_map(|row| row.record_id.parse::<i64>().ok())
            .max()
            .unwrap_or(0);
        Ok(max_id + 1)
    }
}
