//! 渠道 Provider 共享层（两站共用）。

pub mod account;
pub mod account_qr;
pub mod cookies;
pub mod db;
pub mod stores;

pub use account::resolve_account_platform;
pub use db::SqliteBusinessDb;
pub use stores::{
    InMemoryAccountStore, InMemoryItemStore, InMemoryMonitorResultStore, InMemoryMonitorRunStore,
    InMemoryMonitorTaskStore, InMemoryOrderStore, InMemoryRiskStore, InMemoryUserSettingStore,
};
