//! 闲鱼业务存储 — 从 `platform_core` 统一 re-export。
//!
//! 所有 SQLite 存储适配器已集中在 `crates/platform/src/shared/stores.rs` 单文件实现，
//! 此处不再按域拆分子模块，避免同一业务散落多文件。
//!
//! 精简说明：仅保留已接入功能（账号 / 商品 / 订单 / 风控 / 用户设置）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub use crate::core::store::{
    InMemoryAccountStore, InMemoryItemStore, InMemoryOrderStore, InMemoryRiskStore,
    InMemoryUserSettingStore,
};
