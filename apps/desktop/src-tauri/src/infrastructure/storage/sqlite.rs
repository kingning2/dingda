//! Generic SQLite infrastructure — connection management and migrations.

use std::path::Path;

use diesel::connection::SimpleConnection;
use diesel::Connection;
use diesel::SqliteConnection;
use diesel_migrations::{FileBasedMigrations, MigrationHarness};
use thiserror::Error;

/// Storage layer errors.
#[derive(Debug, Error)]
pub enum StorageError {
    #[error("open database failed: {0}")]
    Open(String),
    #[error("migration failed: {0}")]
    Migration(String),
    #[error("lock poisoned: {0}")]
    Poisoned(String),
}

/// A process-local SQLite database handle.
///
/// Holds a single connection behind a mutex; heavy concurrent writers should
/// pool connections instead. Migrations are run lazily via [`SqliteDb::migrate`].
pub struct SqliteDb {
    conn: std::sync::Mutex<SqliteConnection>,
}

impl SqliteDb {
    /// Open (and create if missing) a SQLite database at `path`.
    pub fn open(path: &Path) -> Result<Self, StorageError> {
        let path_str = path
            .to_str()
            .ok_or_else(|| StorageError::Open("path is not valid UTF-8".into()))?;

        let mut conn = SqliteConnection::establish(path_str)
            .map_err(|error| StorageError::Open(error.to_string()))?;

        conn.batch_execute("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")
            .map_err(|error| StorageError::Open(error.to_string()))?;

        Ok(Self {
            conn: std::sync::Mutex::new(conn),
        })
    }

    /// Run pending migrations from `dir` (diesel `migrations/` layout).
    pub fn migrate(&self, dir: &Path) -> Result<(), StorageError> {
        let mut conn = self
            .conn
            .lock()
            .map_err(|error| StorageError::Poisoned(error.to_string()))?;
        let migrations = FileBasedMigrations::from_path(dir)
            .map_err(|error| StorageError::Migration(error.to_string()))?;
        conn.run_pending_migrations(migrations)
            .map_err(|error| StorageError::Migration(error.to_string()))?;
        Ok(())
    }

    /// Access the guarded connection for business CRUD.
    pub fn connection(&self) -> Result<std::sync::MutexGuard<'_, SqliteConnection>, StorageError> {
        self.conn
            .lock()
            .map_err(|error| StorageError::Poisoned(error.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use diesel::RunQueryDsl;

    #[test]
    fn open_and_create_wal_db() {
        let dir = std::env::temp_dir().join(format!("dingda-storage-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).ok();
        let db = SqliteDb::open(&dir.join("test.db")).expect("open should succeed");
        let mut conn = db.connection().expect("lock");
        diesel::sql_query("SELECT 1").execute(&mut *conn).ok();
    }
}
