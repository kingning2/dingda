//! 订单管理 Tauri commands — 订单查询/状态/发货/评价联动。
//!
//! 壳层组合：`InMemoryOrderStore` → `crate::core::domain::order::OrderService`。

use crate::cmd::IpcResponse;
use crate::core::domain::order::{DeliveryInfoUpdate, Order, OrderService, OrderStatus};
use crate::feat::xianyu::persist::InMemoryOrderStore;
use serde::Deserialize;
use std::sync::Arc;
use tauri::State;

/// 订单服务句柄（setup 时注册到 Tauri 状态）。
pub struct OrderHandle {
    pub store: Arc<InMemoryOrderStore>,
}

#[derive(Debug, Deserialize)]
pub struct OrderListRequest {
    pub owner_id: i64,
    pub page: u32,
    pub page_size: u32,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub keyword: String,
    /// 按买家 ID 过滤（客户会话客户信息栏使用；空串 = 不过滤）。
    #[serde(default)]
    pub buyer_id: String,
}

#[derive(Debug, Deserialize)]
pub struct OrderStatusRequest {
    pub order_no: String,
    pub status: String,
}

#[derive(Debug, Deserialize)]
pub struct OrderDeliveryRequest {
    pub order_no: String,
    pub status: String,
    pub delivery_method: String,
    pub delivery_content: Option<String>,
}

#[tauri::command]
pub fn order_list(
    state: State<'_, OrderHandle>,
    request: OrderListRequest,
) -> crate::contracts::DingDaResult<IpcResponse<(Vec<Order>, u32)>> {
    let service = OrderService::new(state.store.as_ref());
    let status = request.status.as_deref().map(OrderStatus::from_str);
    let buyer_id = if request.buyer_id.is_empty() {
        None
    } else {
        Some(request.buyer_id.as_str())
    };
    let result = service
        .list(
            request.owner_id,
            request.page,
            request.page_size,
            status,
            &request.keyword,
            buyer_id,
        )
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn order_get(
    state: State<'_, OrderHandle>,
    owner_id: i64,
    order_no: String,
) -> crate::contracts::DingDaResult<IpcResponse<Option<Order>>> {
    let service = OrderService::new(state.store.as_ref());
    let result = service
        .get_order_by_no(owner_id, &order_no)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn order_update_status(
    state: State<'_, OrderHandle>,
    request: OrderStatusRequest,
) -> crate::contracts::DingDaResult<IpcResponse<bool>> {
    let service = OrderService::new(state.store.as_ref());
    let status = OrderStatus::from_str(&request.status);
    let result = service
        .update_status(&request.order_no, status)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn order_update_delivery(
    state: State<'_, OrderHandle>,
    request: OrderDeliveryRequest,
) -> crate::contracts::DingDaResult<IpcResponse<bool>> {
    let service = OrderService::new(state.store.as_ref());
    let update = DeliveryInfoUpdate {
        status: OrderStatus::from_str(&request.status),
        delivery_method: crate::core::domain::order::DeliveryMethod::from_str(
            &request.delivery_method,
        ),
        delivery_content: request.delivery_content.clone(),
        buyer_fish_nick: None,
    };
    let result = service
        .update_delivery_info(&request.order_no, update)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn order_create(
    state: State<'_, OrderHandle>,
    order: Order,
) -> crate::contracts::DingDaResult<IpcResponse<Order>> {
    let service = OrderService::new(state.store.as_ref());
    let result = service
        .create(&order)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn order_delete(
    state: State<'_, OrderHandle>,
    owner_id: i64,
    order_id: i64,
) -> crate::contracts::DingDaResult<IpcResponse<bool>> {
    let service = OrderService::new(state.store.as_ref());
    let result = service
        .delete(owner_id, order_id)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}
