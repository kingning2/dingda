//! 闲鱼业务 SQLite 存储适配器集合。
//!
//! 将所有业务域的存储适配器集中到一个文件，通过 `SqliteBusinessDb` 统一持久化。
//! 每个 `InMemory*Store` 结构体对应一个业务域（domain），实现各自的 Port 接口。
//!
//! 业务域映射（仅保留已接入功能）：
//! - `account` → [`InMemoryAccountStore`]
//! - `item`    → [`InMemoryItemStore`]
//! - `order`   → [`InMemoryOrderStore`]
//! - `risk`    → [`InMemoryRiskStore`]
//! - `setting` → [`InMemoryUserSettingStore`]
//!
//! 精简说明：发布 / 卡券 / 黑名单 / 关键词 / 消息过滤 / 通知 / 反馈 / 自动回复日志
//! / 批量任务等子页已下线，对应 Store 一并删除。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::infrastructure::database::connection::SqliteBusinessDb;

use crate::contracts::{DingDaError, DingDaResult};
use crate::domain::account::{AccountStore, XianyuAccount};
use crate::domain::item::{Item, ItemQuery, ItemStore};
use crate::domain::order::{DeliveryInfoUpdate, Order, OrderStatus, OrderStore};
use crate::domain::risk::{RiskConfig, RiskLogItem, RiskLogQuery, RiskStore};
use crate::domain::setting::UserSettingStore;
use diesel::sql_types::Text;
use diesel::{QueryableByName, RunQueryDsl};

// ─── 账号 ──────────────────────────────────────────────────────────────────────

/// SQLite 账号存储，实现 [`AccountStore`]。记录落 `business_records(domain="account")`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct InMemoryAccountStore {
    db: SqliteBusinessDb,
}

impl InMemoryAccountStore {
    /// 以已初始化的业务数据库构建存储。
    pub fn new(db: SqliteBusinessDb) -> Self {
        Self { db }
    }
}

const DOMAIN_ACCOUNT: &str = "account";

impl AccountStore for InMemoryAccountStore {
    fn get_account(&self, owner_id: i64, account_id: &str) -> DingDaResult<Option<XianyuAccount>> {
        Ok(self.db.get(DOMAIN_ACCOUNT, account_id, owner_id)?)
    }

    fn list_accounts(&self, owner_id: i64) -> DingDaResult<Vec<XianyuAccount>> {
        Ok(self.db.scan(DOMAIN_ACCOUNT, owner_id)?)
    }

    fn create_account(&self, account: &XianyuAccount) -> DingDaResult<XianyuAccount> {
        let mut account = account.clone();
        if account.id == 0 {
            account.id = self.db.next_id(DOMAIN_ACCOUNT, account.owner_id)?;
        }
        self.db.put(
            DOMAIN_ACCOUNT,
            &account.account_id,
            account.owner_id,
            &account,
        )?;
        Ok(account)
    }

    fn update_account(&self, account: &XianyuAccount) -> DingDaResult<()> {
        if self
            .db
            .get::<XianyuAccount>(DOMAIN_ACCOUNT, &account.account_id, account.owner_id)?
            .is_none()
        {
            return Err(format!("账号 {} 不存在", account.account_id).into());
        }
        Ok(self.db.put(
            DOMAIN_ACCOUNT,
            &account.account_id,
            account.owner_id,
            account,
        )?)
    }

    fn delete_account(&self, owner_id: i64, account_id: &str) -> DingDaResult<()> {
        Ok(self.db.delete(DOMAIN_ACCOUNT, account_id, owner_id)?)
    }

    fn find_by_account_id(&self, account_id: &str) -> DingDaResult<Option<XianyuAccount>> {
        let mut conn = self.db.connection()?;
        #[derive(QueryableByName)]
        struct PayloadRow {
            #[diesel(sql_type = Text)]
            payload: String,
        }
        let rows: Vec<PayloadRow> = diesel::sql_query(
            "SELECT payload FROM business_records WHERE domain = ? AND record_id = ?",
        )
        .bind::<Text, _>(DOMAIN_ACCOUNT)
        .bind::<Text, _>(account_id)
        .load(&mut *conn)
        .map_err(|e| DingDaError::Store(e.to_string()))?;
        rows.into_iter()
            .next()
            .map_or(Ok(None), |row| Ok(serde_json::from_str(&row.payload)?))
    }
}

// ─── 商品 ──────────────────────────────────────────────────────────────────────

/// SQLite 商品存储，实现 [`ItemStore`]。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct InMemoryItemStore {
    db: SqliteBusinessDb,
}

impl InMemoryItemStore {
    pub fn new(db: SqliteBusinessDb) -> Self {
        Self { db }
    }
}

const DOMAIN_ITEM: &str = "item";

impl ItemStore for InMemoryItemStore {
    fn list_items(&self, owner_id: i64, query: &ItemQuery) -> DingDaResult<(Vec<Item>, u32)> {
        let items: Vec<Item> = self.db.scan(DOMAIN_ITEM, owner_id)?;
        let mut list: Vec<Item> = items
            .into_iter()
            .filter(|item| {
                item.owner_id == owner_id
                    && (query.account_id.is_empty() || item.account_id == query.account_id)
                    && (query.keyword.is_empty()
                        || item.item_id.contains(&query.keyword)
                        || item.title.contains(&query.keyword))
                    && query
                        .is_polished
                        .map(|v| item.is_polished == v)
                        .unwrap_or(true)
                    && query
                        .is_multi_spec
                        .map(|v| item.is_multi_spec == v)
                        .unwrap_or(true)
            })
            .collect();
        list.sort_by_key(|item| std::cmp::Reverse(item.id));
        let total = list.len() as u32;
        Ok((list, total))
    }

    fn get_item(&self, owner_id: i64, item_id: &str) -> DingDaResult<Option<Item>> {
        Ok(self.db.get(DOMAIN_ITEM, item_id, owner_id)?)
    }

    fn update_item(&self, item: &Item) -> DingDaResult<()> {
        if self
            .db
            .get::<Item>(DOMAIN_ITEM, &item.item_id, item.owner_id)?
            .is_none()
        {
            return Err(format!("商品 {} 不存在", item.item_id).into());
        }
        Ok(self
            .db
            .put(DOMAIN_ITEM, &item.item_id, item.owner_id, item)?)
    }

    fn upsert_item(&self, item: &Item) -> DingDaResult<()> {
        if let Some(mut existing) = self.get_item(item.owner_id, &item.item_id)? {
            existing.title = item.title.clone();
            existing.price = item.price;
            existing.desc = item.desc.clone();
            existing.account_id = item.account_id.clone();
            Ok(self
                .db
                .put(DOMAIN_ITEM, &existing.item_id, existing.owner_id, &existing)?)
        } else {
            let mut item = item.clone();
            if item.id == 0 {
                item.id = self.db.next_id(DOMAIN_ITEM, item.owner_id)?;
            }
            Ok(self
                .db
                .put(DOMAIN_ITEM, &item.item_id, item.owner_id, &item)?)
        }
    }
}

// ─── 订单 ──────────────────────────────────────────────────────────────────────

/// SQLite 订单存储，实现 [`OrderStore`]。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct InMemoryOrderStore {
    db: SqliteBusinessDb,
}

impl InMemoryOrderStore {
    pub fn new(db: SqliteBusinessDb) -> Self {
        Self { db }
    }

    fn put_order(&self, order: &Order) -> DingDaResult<()> {
        Ok(self
            .db
            .put(DOMAIN_ORDER, &order.order_no, order.owner_id, order)?)
    }
}

const DOMAIN_ORDER: &str = "order";

impl OrderStore for InMemoryOrderStore {
    fn get_order(&self, order_no: &str) -> DingDaResult<Option<Order>> {
        let mut conn = self.db.connection()?;
        #[derive(QueryableByName)]
        struct PayloadRow {
            #[diesel(sql_type = Text)]
            payload: String,
        }
        let rows: Vec<PayloadRow> = diesel::sql_query(
            "SELECT payload FROM business_records WHERE domain = ? AND record_id = ?",
        )
        .bind::<Text, _>(DOMAIN_ORDER)
        .bind::<Text, _>(order_no)
        .load(&mut *conn)
        .map_err(|e| DingDaError::Store(e.to_string()))?;
        rows.into_iter()
            .next()
            .map_or(Ok(None), |row| Ok(serde_json::from_str(&row.payload)?))
    }

    fn get_order_by_no(&self, owner_id: i64, order_no: &str) -> DingDaResult<Option<Order>> {
        Ok(self.db.get(DOMAIN_ORDER, order_no, owner_id)?)
    }

    fn get_pending_order_by_buyer(
        &self,
        owner_id: i64,
        account_id: &str,
        buyer_id: &str,
        item_id: Option<&str>,
    ) -> DingDaResult<Option<Order>> {
        let orders: Vec<Order> = self.db.scan(DOMAIN_ORDER, owner_id)?;
        Ok(orders.into_iter().find(|order| {
            order.owner_id == owner_id
                && order.account_id == account_id
                && order.buyer_id == buyer_id
                && order.status.is_pending_ship()
                && item_id.map(|id| order.item_id == id).unwrap_or(true)
        }))
    }

    fn list_orders(
        &self,
        owner_id: i64,
        _page: u32,
        _page_size: u32,
        status: Option<OrderStatus>,
        keyword: &str,
        buyer_id: Option<&str>,
    ) -> DingDaResult<(Vec<Order>, u32)> {
        let orders: Vec<Order> = self.db.scan(DOMAIN_ORDER, owner_id)?;
        let mut list: Vec<Order> = orders
            .into_iter()
            .filter(|order| {
                order.owner_id == owner_id
                    && status.map(|s| order.status == s).unwrap_or(true)
                    && buyer_id.is_none_or(|b| order.buyer_id == b)
                    && (keyword.is_empty()
                        || order.order_no.contains(keyword)
                        || order.buyer_nick.contains(keyword)
                        || order.item_title.contains(keyword))
            })
            .collect();
        list.sort_by_key(|order| std::cmp::Reverse(order.id));
        let total = list.len() as u32;
        Ok((list, total))
    }

    fn update_status(&self, order_no: &str, status: OrderStatus) -> DingDaResult<bool> {
        let Some(mut order) = self.get_order(order_no)? else {
            return Ok(false);
        };
        order.status = status;
        self.put_order(&order)?;
        Ok(true)
    }

    fn update_chat_id(&self, order_no: &str, chat_id: &str) -> DingDaResult<bool> {
        let Some(mut order) = self.get_order(order_no)? else {
            return Ok(false);
        };
        order.chat_id = chat_id.to_string();
        self.put_order(&order)?;
        Ok(true)
    }

    fn update_delivery_info(
        &self,
        order_no: &str,
        update: &DeliveryInfoUpdate,
    ) -> DingDaResult<bool> {
        let Some(mut order) = self.get_order(order_no)? else {
            return Ok(false);
        };
        order.status = update.status;
        order.delivery_method = Some(update.delivery_method);
        order.delivery_content = update.delivery_content.clone().unwrap_or_default();
        order.delivery_fail_reason.clear();
        if let Some(nick) = &update.buyer_fish_nick {
            order.buyer_fish_nick = nick.clone();
        }
        self.put_order(&order)?;
        Ok(true)
    }

    fn update_delivery_fail_reason(&self, order_no: &str, reason: &str) -> DingDaResult<bool> {
        let Some(mut order) = self.get_order(order_no)? else {
            return Ok(false);
        };
        order.delivery_fail_reason = reason.to_string();
        self.put_order(&order)?;
        Ok(true)
    }

    fn update_rated(&self, order_no: &str, is_rated: bool) -> DingDaResult<bool> {
        let Some(mut order) = self.get_order(order_no)? else {
            return Ok(false);
        };
        order.is_rated = is_rated;
        self.put_order(&order)?;
        Ok(true)
    }

    fn create_order(&self, order: &Order) -> DingDaResult<Order> {
        let mut order = order.clone();
        let orders: Vec<Order> = self.db.scan(DOMAIN_ORDER, order.owner_id)?;
        order.id = orders.iter().map(|o| o.id).max().unwrap_or(0) + 1;
        self.put_order(&order)?;
        Ok(order)
    }

    fn delete_order(&self, owner_id: i64, order_id: i64) -> DingDaResult<bool> {
        let orders: Vec<Order> = self.db.scan(DOMAIN_ORDER, owner_id)?;
        let matched: Vec<String> = orders
            .into_iter()
            .filter(|o| o.id == order_id)
            .map(|o| o.order_no)
            .collect();
        let deleted = !matched.is_empty();
        for order_no in matched {
            self.db.delete(DOMAIN_ORDER, &order_no, owner_id)?;
        }
        Ok(deleted)
    }

    fn batch_delete_orders(&self, owner_id: i64, order_ids: &[i64]) -> DingDaResult<u32> {
        let orders: Vec<Order> = self.db.scan(DOMAIN_ORDER, owner_id)?;
        let matched: Vec<String> = orders
            .into_iter()
            .filter(|o| order_ids.contains(&o.id))
            .map(|o| o.order_no)
            .collect();
        let count = matched.len() as u32;
        for order_no in matched {
            self.db.delete(DOMAIN_ORDER, &order_no, owner_id)?;
        }
        Ok(count)
    }
}

// ─── 风控 ──────────────────────────────────────────────────────────────────────

/// SQLite 风控存储，实现 [`RiskStore`]。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct InMemoryRiskStore {
    db: SqliteBusinessDb,
}

impl InMemoryRiskStore {
    pub fn new(db: SqliteBusinessDb) -> Self {
        Self { db }
    }
}

const DOMAIN_RISK: &str = "risk";
const DOMAIN_RISK_CONFIG: &str = "risk_config";
const RISK_CONFIG_KEY: &str = "config";

impl RiskStore for InMemoryRiskStore {
    fn list_logs(&self, owner_id: i64, query: &RiskLogQuery) -> DingDaResult<Vec<RiskLogItem>> {
        let logs: Vec<RiskLogItem> = self.db.scan(DOMAIN_RISK, owner_id)?;
        let mut list: Vec<RiskLogItem> =
            logs.into_iter()
                .filter(|log| {
                    (query.account_id.is_empty() || log.account_id == query.account_id)
                        && (query.start_date.is_empty()
                            || log
                                .created_at
                                .as_deref()
                                .is_none_or(|t| t >= query.start_date.as_str()))
                        && (query.end_date.is_empty()
                            || log.created_at.as_deref().is_none_or(|t| {
                                t <= format!("{} 23:59:59", query.end_date).as_str()
                            }))
                        && (query.processing_status.is_empty()
                            || log.processing_status == query.processing_status)
                        && (query.call_type.is_empty()
                            || log.call_type.as_deref() == Some(query.call_type.as_str()))
                        && (query.call_user.is_empty()
                            || log.call_user.as_deref() == Some(query.call_user.as_str()))
                })
                .collect();
        list.sort_by_key(|log| log.id);
        Ok(list)
    }

    fn clear_logs(&self, owner_id: i64, account_id: &str) -> DingDaResult<()> {
        let logs: Vec<RiskLogItem> = self.db.scan(DOMAIN_RISK, owner_id)?;
        for log in logs {
            if account_id.is_empty() || log.account_id == account_id {
                self.db.delete(DOMAIN_RISK, &log.id.to_string(), owner_id)?;
            }
        }
        Ok(())
    }

    fn clear_processing(&self, owner_id: i64) -> DingDaResult<()> {
        let logs: Vec<RiskLogItem> = self.db.scan(DOMAIN_RISK, owner_id)?;
        for log in logs {
            if log.processing_status == "processing" {
                self.db.delete(DOMAIN_RISK, &log.id.to_string(), owner_id)?;
            }
        }
        Ok(())
    }

    fn get_config(&self, owner_id: i64) -> DingDaResult<RiskConfig> {
        Ok(self
            .db
            .get(DOMAIN_RISK_CONFIG, RISK_CONFIG_KEY, owner_id)?
            .unwrap_or_default())
    }

    fn save_config(&self, owner_id: i64, config: &RiskConfig) -> DingDaResult<()> {
        Ok(self
            .db
            .put(DOMAIN_RISK_CONFIG, RISK_CONFIG_KEY, owner_id, config)?)
    }

    fn append_log(&self, mut log: RiskLogItem) -> DingDaResult<RiskLogItem> {
        if log.id == 0 {
            log.id = self.db.next_id(DOMAIN_RISK, log.owner_id)?;
        }
        self.db
            .put(DOMAIN_RISK, &log.id.to_string(), log.owner_id, &log)?;
        Ok(log)
    }

    fn update_log(&self, log: &RiskLogItem) -> DingDaResult<()> {
        if log.id == 0 {
            return Err("更新风控日志缺少 id".into());
        }
        self.db
            .put(DOMAIN_RISK, &log.id.to_string(), log.owner_id, log)?;
        Ok(())
    }
}

// ─── 用户设置 ──────────────────────────────────────────────────────────────────

/// SQLite 用户设置存储，实现 [`UserSettingStore`]。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct InMemoryUserSettingStore {
    db: SqliteBusinessDb,
}

impl InMemoryUserSettingStore {
    pub fn new(db: SqliteBusinessDb) -> Self {
        Self { db }
    }
}

const DOMAIN_SETTING: &str = "setting";

impl UserSettingStore for InMemoryUserSettingStore {
    fn get(&self, owner_id: i64, key: &str) -> DingDaResult<Option<String>> {
        Ok(self.db.get(DOMAIN_SETTING, key, owner_id)?)
    }

    fn set(&self, owner_id: i64, key: &str, value: &str) -> DingDaResult<()> {
        if value.is_empty() {
            Ok(self.db.delete(DOMAIN_SETTING, key, owner_id)?)
        } else {
            Ok(self
                .db
                .put(DOMAIN_SETTING, key, owner_id, &value.to_string())?)
        }
    }
}
