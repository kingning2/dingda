//! 闲鱼交易 IPC — 商品管理 / 商品同步 / 商品详情 / 订单管理。

use crate::bootstrap::state::AppState;
use crate::commands::AccountHandle;
use crate::commands::IpcResponse;
use crate::domain::account::{AccountService, AccountStore, AccountUpdate, XianyuAccount};
use crate::domain::item::{Item, ItemQuery, ItemService};
use crate::domain::order::{DeliveryInfoUpdate, Order, OrderService, OrderStatus};
use crate::infrastructure::database::{InMemoryItemStore, InMemoryOrderStore};
use crate::infrastructure::sidecar::channel_product::{
    item_detail, seller_items, ItemDetailRequest, PlatformItemDetailDto, SellerItemsRequest,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tauri::State;
use tracing::{info, warn};

/// 商品服务句柄（setup 时注册到 Tauri 状态）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
pub struct ItemHandle {
    pub store: Arc<InMemoryItemStore>,
}

#[derive(Debug, Deserialize)]
pub struct ItemListRequest {
    pub owner_id: i64,
    pub page: u32,
    pub page_size: u32,
    #[serde(default)]
    pub keyword: String,
    #[serde(default)]
    pub account_id: String,
    pub is_polished: Option<bool>,
    pub is_multi_spec: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct ItemUpdateRequest {
    pub owner_id: i64,
    pub item_id: String,
    pub ai_prompt: Option<String>,
}

/// 商品同步请求。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[derive(Debug, Deserialize)]
pub struct ItemSyncRequest {
    pub owner_id: i64,
    /// 为空时同步全部有 Cookie 的账号。
    #[serde(default)]
    pub account_id: String,
}

/// 商品同步结果。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[derive(Debug, Clone, Serialize)]
pub struct ItemSyncResult {
    /// 处理商品总数（新建 + 更新）。
    pub synced: u32,
    /// 新建数量。
    pub created: u32,
    /// 更新数量。
    pub updated: u32,
}

#[tauri::command]
pub fn item_list(
    state: State<'_, ItemHandle>,
    request: ItemListRequest,
) -> crate::contracts::DingDaResult<IpcResponse<(Vec<Item>, u32)>> {
    let service = ItemService::new(state.store.as_ref());
    let query = ItemQuery {
        page: request.page,
        page_size: request.page_size,
        keyword: request.keyword,
        account_id: request.account_id,
        is_polished: request.is_polished,
        is_multi_spec: request.is_multi_spec,
    };
    let result = service
        .list(request.owner_id, &query)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn item_get(
    state: State<'_, ItemHandle>,
    owner_id: i64,
    item_id: String,
) -> crate::contracts::DingDaResult<IpcResponse<Option<Item>>> {
    let service = ItemService::new(state.store.as_ref());
    let result = service
        .get(owner_id, &item_id)
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

#[tauri::command]
pub fn item_update(
    state: State<'_, ItemHandle>,
    request: ItemUpdateRequest,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    let service = ItemService::new(state.store.as_ref());
    service
        .update(request.owner_id, &request.item_id, |item| {
            if let Some(ai_prompt) = &request.ai_prompt {
                item.ai_prompt = ai_prompt.clone();
            }
        })
        .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(()))
}

/// 从闲鱼平台拉取在售商品并写入本地库。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
///
/// # 参数
///
/// * `items` — 商品存储句柄
/// * `accounts` — 账号存储句柄
/// * `request` — 同步请求（可指定单账号或全部）
///
/// # 返回值
///
/// 成功返回同步统计；账号缺失 Cookie 或平台接口失败返回错误。
#[tauri::command]
pub async fn item_sync(
    state: State<'_, AppState>,
    items: State<'_, ItemHandle>,
    accounts: State<'_, AccountHandle>,
    request: ItemSyncRequest,
) -> crate::contracts::DingDaResult<IpcResponse<ItemSyncResult>> {
    let account_service = AccountService::new(accounts.store.as_ref());
    let item_service = ItemService::new(items.store.as_ref());

    let targets: Vec<XianyuAccount> = if request.account_id.trim().is_empty() {
        account_service
            .list(request.owner_id)
            .map_err(crate::contracts::DingDaError::wrap)?
            .into_iter()
            .filter(|account| account.has_cookie())
            .collect()
    } else {
        let account = accounts
            .store
            .get_account(request.owner_id, &request.account_id)
            .map_err(crate::contracts::DingDaError::wrap)?
            .ok_or_else(|| format!("账号不存在: {}", request.account_id))?;
        if !account.has_cookie() {
            return Err("账号缺少 Cookie，请先扫码登录".into());
        }
        vec![account]
    };

    if targets.is_empty() {
        return Err("没有可同步的账号（需先连接并登录）".into());
    }

    state
        .lifecycle
        .ensure_running()
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    let mut synced = 0u32;
    let mut created = 0u32;
    let mut updated = 0u32;

    for account in targets {
        let cookie_header =
            crate::infrastructure::database::cookies::credential_to_cookie_header(&account.cookie);
        let user_id = {
            let from_account = account.extract_unb();
            if !from_account.is_empty() {
                from_account
            } else {
                crate::infrastructure::database::cookies::my_id(
                    &crate::infrastructure::database::cookies::parse_credential(&cookie_header),
                )
                .unwrap_or_default()
            }
        };
        if user_id.is_empty() {
            warn!(account = %account.account_id, "账号缺少 unb，跳过商品同步");
            continue;
        }

        let cookie_for_fetch = if cookie_header.contains("unb=") {
            cookie_header
        } else {
            format!("unb={user_id}; {cookie_header}")
        };

        let response = seller_items(
            state.lifecycle.client(),
            SellerItemsRequest {
                cookie: cookie_for_fetch,
                user_id,
                max_pages: 0,
            },
        )
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
        if !response.ok {
            return Err(crate::contracts::DingDaError::wrap(
                response
                    .message
                    .unwrap_or_else(|| "商品同步失败".to_string()),
            ));
        }
        let platform_items = response.items;
        if let Some(updated_cookie) = response.cookie {
            if updated_cookie != account.cookie {
                account_service
                    .update(
                        request.owner_id,
                        &account.account_id,
                        &AccountUpdate {
                            cookie: Some(updated_cookie),
                            ..Default::default()
                        },
                    )
                    .map_err(crate::contracts::DingDaError::wrap)?;
            }
        }

        for platform_item in platform_items {
            let existed = item_service
                .get(request.owner_id, &platform_item.item_id)
                .map_err(crate::contracts::DingDaError::wrap)?
                .is_some();

            let item = Item {
                id: 0,
                owner_id: request.owner_id,
                account_id: account.account_id.clone(),
                item_id: platform_item.item_id,
                title: platform_item.title,
                price: platform_item.price,
                desc: platform_item.desc,
                is_polished: false,
                is_multi_spec: false,
                multi_quantity_delivery: false,
                ai_prompt: String::new(),
                has_card: false,
                has_default_reply: false,
                created_at: None,
            };

            item_service
                .upsert(&item)
                .map_err(crate::contracts::DingDaError::wrap)?;

            synced += 1;
            if existed {
                updated += 1;
            } else {
                created += 1;
            }
        }

        info!(
            account = %account.account_id,
            synced,
            created,
            updated,
            "闲鱼商品同步完成"
        );
    }

    Ok(IpcResponse::ok(ItemSyncResult {
        synced,
        created,
        updated,
    }))
}

/// 商品详情拉取请求。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[derive(Debug, Deserialize)]
pub struct ItemDetailFetchRequest {
    pub owner_id: i64,
    pub item_id: String,
    /// 为空时从本地商品记录读取 account_id。
    #[serde(default)]
    pub account_id: String,
}

/// 从闲鱼平台拉取商品详情（`mtop.taobao.idle.pc.detail`）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn item_detail_fetch(
    state: State<'_, AppState>,
    items: State<'_, ItemHandle>,
    accounts: State<'_, AccountHandle>,
    request: ItemDetailFetchRequest,
) -> crate::contracts::DingDaResult<IpcResponse<PlatformItemDetailDto>> {
    let item_service = ItemService::new(items.store.as_ref());
    let account_service = AccountService::new(accounts.store.as_ref());

    let account_id = if request.account_id.trim().is_empty() {
        item_service
            .get(request.owner_id, &request.item_id)
            .map_err(crate::contracts::DingDaError::wrap)?
            .map(|item| item.account_id)
            .ok_or_else(|| format!("本地未找到商品 {}，请先同步", request.item_id))?
    } else {
        request.account_id.clone()
    };

    let account = accounts
        .store
        .get_account(request.owner_id, &account_id)
        .map_err(crate::contracts::DingDaError::wrap)?
        .ok_or_else(|| format!("账号不存在: {account_id}"))?;
    if !account.has_cookie() {
        return Err("账号缺少 Cookie，请先扫码登录".into());
    }

    state
        .lifecycle
        .ensure_running()
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    let response = item_detail(
        state.lifecycle.client(),
        ItemDetailRequest {
            cookie: crate::infrastructure::database::cookies::credential_to_cookie_header(
                &account.cookie,
            ),
            item_id: request.item_id.clone(),
        },
    )
    .await
    .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
    if !response.ok {
        return Err(crate::contracts::DingDaError::wrap(
            response
                .message
                .unwrap_or_else(|| "商品详情拉取失败".to_string()),
        ));
    }
    let detail = response
        .detail
        .ok_or_else(|| crate::contracts::DingDaError::wrap("商品详情为空".to_string()))?;

    if let Some(updated_cookie) = response.cookie {
        if updated_cookie != account.cookie {
            account_service
                .update(
                    request.owner_id,
                    &account_id,
                    &AccountUpdate {
                        cookie: Some(updated_cookie),
                        ..Default::default()
                    },
                )
                .map_err(crate::contracts::DingDaError::wrap)?;
        }
    }

    Ok(IpcResponse::ok(detail))
}

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
        delivery_method: crate::domain::order::DeliveryMethod::from_str(&request.delivery_method),
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
