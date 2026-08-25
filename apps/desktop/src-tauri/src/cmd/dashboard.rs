//! 仪表盘统计 Tauri commands。

use crate::cmd::IpcResponse;
use crate::core::domain::account::AccountStore;
use crate::core::domain::item::{ItemQuery, ItemStore};
use crate::core::domain::order::{OrderStatus, OrderStore};
use crate::feat::xianyu::persist::InMemoryAccountStore;
use crate::feat::xianyu::persist::InMemoryItemStore;
use crate::feat::xianyu::persist::InMemoryOrderStore;
use serde::Serialize;
use std::sync::Arc;
use tauri::State;

#[derive(Debug, Clone, Default, Serialize)]
pub struct DashboardStats {
    pub total_accounts: u32,
    pub active_accounts: u32,
    pub total_items: u32,
    pub total_orders: u32,
    pub pending_ship_orders: u32,
}

pub struct DashboardHandle {
    pub accounts: Arc<InMemoryAccountStore>,
    pub items: Arc<InMemoryItemStore>,
    pub orders: Arc<InMemoryOrderStore>,
}

impl DashboardHandle {
    pub fn stats(&self, owner_id: i64) -> DashboardStats {
        let accounts = self.accounts.list_accounts(owner_id).unwrap_or_default();
        let total_accounts = accounts.len() as u32;
        let active_accounts = accounts
            .iter()
            .filter(|account| account.is_active())
            .count() as u32;

        let item_query = ItemQuery {
            page: 1,
            page_size: 1,
            ..Default::default()
        };
        let (_, total_items) = self
            .items
            .list_items(owner_id, &item_query)
            .unwrap_or((Vec::new(), 0));

        let (_, total_orders) = self
            .orders
            .list_orders(owner_id, 1, 1, None, "", None)
            .unwrap_or((Vec::new(), 0));

        let (_, pending_ship_orders) = self
            .orders
            .list_orders(owner_id, 1, u32::MAX, Some(OrderStatus::Paid), "", None)
            .unwrap_or((Vec::new(), 0));

        DashboardStats {
            total_accounts,
            active_accounts,
            total_items,
            total_orders,
            pending_ship_orders,
        }
    }
}

#[tauri::command]
pub fn dashboard_stats(
    state: State<'_, DashboardHandle>,
    owner_id: i64,
) -> crate::contracts::DingDaResult<IpcResponse<DashboardStats>> {
    Ok(IpcResponse::ok(state.stats(owner_id)))
}
