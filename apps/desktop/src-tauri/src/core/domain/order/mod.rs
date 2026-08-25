//! 订单管理 — 订单领域模型 + 状态与 CRUD 服务。
//!
//! 对齐 Python 版 `xy_order` 模型与 `order_service.py` 核心业务：
//! - 订单状态（待付款/待发货/已发货/已关闭/已退款等，兼容中英文状态）；
//! - 发货信息更新（状态/方式/内容/失败原因，内容截断 2000）；
//! - 买家维度查询（待发货订单，供自动发货/评价联动）；
//! - 归属校验（owner_id）+ 批量删除。

use crate::contracts::DingDaResult;
use serde::{Deserialize, Serialize};

#[cfg(test)]
mod service;

/// 订单状态（兼容 Python 版中英文状态值）。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OrderStatus {
    /// 待付款。
    Pending,
    /// 已付款 / 待发货。
    Paid,
    /// 已发货。
    Shipped,
    /// 已完成 / 交易成功。
    Completed,
    /// 已关闭 / 已取消。
    Closed,
    /// 已退款。
    Refunded,
    /// 未知状态（透传原始字符串）。
    Unknown,
}

impl OrderStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            OrderStatus::Pending => "pending",
            OrderStatus::Paid => "paid",
            OrderStatus::Shipped => "shipped",
            OrderStatus::Completed => "completed",
            OrderStatus::Closed => "closed",
            OrderStatus::Refunded => "refunded",
            OrderStatus::Unknown => "unknown",
        }
    }

    /// 解析状态字符串（兼容中英文 + 闲鱼平台值）。
    #[allow(clippy::should_implement_trait)]
    pub fn from_str(value: &str) -> Self {
        match value.trim().to_lowercase().as_str() {
            "pending" | "待付款" | "待发货" | "wait_pay" => OrderStatus::Pending,
            "paid" | "已付款" | "已拍下" | "wait_ship" => OrderStatus::Paid,
            "shipped" | "已发货" => OrderStatus::Shipped,
            "completed" | "已完成" | "交易成功" | "success" => OrderStatus::Completed,
            "closed" | "已关闭" | "已取消" | "cancelled" | "cancel" => OrderStatus::Closed,
            "refunded" | "已退款" | "退款成功" => OrderStatus::Refunded,
            _ => OrderStatus::Unknown,
        }
    }

    /// 是否属于"待发货"类状态（pending / paid / 待发货），自动发货与评价联动使用。
    pub fn is_pending_ship(&self) -> bool {
        matches!(self, OrderStatus::Pending | OrderStatus::Paid)
    }
}

/// 发货方式。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DeliveryMethod {
    Manual,
    Auto,
    Scheduled,
}

impl DeliveryMethod {
    pub fn as_str(&self) -> &'static str {
        match self {
            DeliveryMethod::Manual => "manual",
            DeliveryMethod::Auto => "auto",
            DeliveryMethod::Scheduled => "scheduled",
        }
    }

    #[allow(clippy::should_implement_trait)]
    pub fn from_str(value: &str) -> Self {
        match value {
            "auto" => DeliveryMethod::Auto,
            "scheduled" => DeliveryMethod::Scheduled,
            _ => DeliveryMethod::Manual,
        }
    }
}

/// 订单（对齐 `xy_orders` 核心字段）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Order {
    pub id: i64,
    pub owner_id: i64,
    pub order_no: String,
    pub status: OrderStatus,
    pub buyer_nick: String,
    pub buyer_fish_nick: String,
    pub buyer_id: String,
    pub chat_id: String,
    pub item_id: String,
    pub item_title: String,
    pub spec_name: String,
    pub spec_value: String,
    pub quantity: u32,
    pub amount: f64,
    pub account_id: String,
    pub account_name: String,
    pub is_bargain: bool,
    /// 是否已评价。
    pub is_rated: bool,
    /// 是否已求小红花。
    pub is_red_flower: bool,
    pub delivery_method: Option<DeliveryMethod>,
    pub delivery_content: String,
    pub delivery_fail_reason: String,
    /// 下单时间（ISO 字符串）。
    pub placed_at: Option<String>,
}

/// 发货信息更新入参。
#[derive(Debug, Clone)]
pub struct DeliveryInfoUpdate {
    pub status: OrderStatus,
    pub delivery_method: DeliveryMethod,
    pub delivery_content: Option<String>,
    pub buyer_fish_nick: Option<String>,
}

/// 发货内容最大长度（对齐 Python 2000 截断）。
pub const DELIVERY_CONTENT_MAX: usize = 2000;

impl Order {
    /// 是否待发货（自动发货/评价联动）。
    pub fn is_pending_ship(&self) -> bool {
        self.status.is_pending_ship()
    }

    /// 归一化发货内容（超长截断，对齐 Python 2000 截断 + 省略号）。
    pub fn normalize_delivery_content(content: &str) -> String {
        if content.chars().count() > DELIVERY_CONTENT_MAX {
            let head: String = content.chars().take(DELIVERY_CONTENT_MAX - 3).collect();
            format!("{head}...")
        } else {
            content.to_string()
        }
    }
}

/// 订单存储 Port。
pub trait OrderStore: Send + Sync {
    /// 按订单号查询。
    fn get_order(&self, order_no: &str) -> DingDaResult<Option<Order>>;

    /// 按订单号 + 归属查询。
    fn get_order_by_no(&self, owner_id: i64, order_no: &str) -> DingDaResult<Option<Order>>;

    /// 按买家查询待发货订单（自动发货/评价联动）。
    fn get_pending_order_by_buyer(
        &self,
        owner_id: i64,
        account_id: &str,
        buyer_id: &str,
        item_id: Option<&str>,
    ) -> DingDaResult<Option<Order>>;

    /// 分页查询订单。
    fn list_orders(
        &self,
        owner_id: i64,
        page: u32,
        page_size: u32,
        status: Option<OrderStatus>,
        keyword: &str,
        buyer_id: Option<&str>,
    ) -> DingDaResult<(Vec<Order>, u32)>;

    /// 更新订单状态。
    fn update_status(&self, order_no: &str, status: OrderStatus) -> DingDaResult<bool>;

    /// 更新订单 chat_id。
    fn update_chat_id(&self, order_no: &str, chat_id: &str) -> DingDaResult<bool>;

    /// 更新发货信息（状态/方式/内容/失败原因）。
    fn update_delivery_info(
        &self,
        order_no: &str,
        update: &DeliveryInfoUpdate,
    ) -> DingDaResult<bool>;

    /// 更新发货失败原因。
    fn update_delivery_fail_reason(&self, order_no: &str, reason: &str) -> DingDaResult<bool>;

    /// 更新评价状态。
    fn update_rated(&self, order_no: &str, is_rated: bool) -> DingDaResult<bool>;

    /// 新建订单。
    fn create_order(&self, order: &Order) -> DingDaResult<Order>;

    /// 删除订单（归属校验）。
    fn delete_order(&self, owner_id: i64, order_id: i64) -> DingDaResult<bool>;

    /// 批量删除订单（归属校验）。
    fn batch_delete_orders(&self, owner_id: i64, order_ids: &[i64]) -> DingDaResult<u32>;
}

/// 订单服务。
pub struct OrderService<'a> {
    store: &'a dyn OrderStore,
}

impl<'a> OrderService<'a> {
    pub fn new(store: &'a dyn OrderStore) -> Self {
        Self { store }
    }

    /// 按订单号查询（内部，无归属过滤）。
    pub fn get_order(&self, order_no: &str) -> DingDaResult<Option<Order>> {
        self.store.get_order(order_no)
    }

    /// 按订单号 + 归属查询。
    pub fn get_order_by_no(&self, owner_id: i64, order_no: &str) -> DingDaResult<Option<Order>> {
        self.store.get_order_by_no(owner_id, order_no)
    }

    /// 买家待发货订单（自动发货/评价联动）。
    pub fn pending_order_by_buyer(
        &self,
        owner_id: i64,
        account_id: &str,
        buyer_id: &str,
        item_id: Option<&str>,
    ) -> DingDaResult<Option<Order>> {
        self.store
            .get_pending_order_by_buyer(owner_id, account_id, buyer_id, item_id)
    }

    /// 分页查询。
    pub fn list(
        &self,
        owner_id: i64,
        page: u32,
        page_size: u32,
        status: Option<OrderStatus>,
        keyword: &str,
        buyer_id: Option<&str>,
    ) -> DingDaResult<(Vec<Order>, u32)> {
        self.store
            .list_orders(owner_id, page, page_size, status, keyword, buyer_id)
    }

    /// 更新状态。
    pub fn update_status(&self, order_no: &str, status: OrderStatus) -> DingDaResult<bool> {
        self.store.update_status(order_no, status)
    }

    /// 更新 chat_id（空值拒绝）。
    pub fn update_chat_id(&self, order_no: &str, chat_id: &str) -> DingDaResult<bool> {
        if chat_id.trim().is_empty() {
            return Err("chat_id 不能为空".to_string().into());
        }
        self.store.update_chat_id(order_no, chat_id.trim())
    }

    /// 更新发货信息（内容自动截断 + 清空失败原因）。
    pub fn update_delivery_info(
        &self,
        order_no: &str,
        mut update: DeliveryInfoUpdate,
    ) -> DingDaResult<bool> {
        if let Some(content) = &update.delivery_content {
            update.delivery_content = Some(Order::normalize_delivery_content(content));
        }
        self.store.update_delivery_info(order_no, &update)
    }

    /// 记录发货失败原因。
    pub fn update_delivery_fail_reason(&self, order_no: &str, reason: &str) -> DingDaResult<bool> {
        self.store.update_delivery_fail_reason(order_no, reason)
    }

    /// 更新评价状态。
    pub fn update_rated(&self, order_no: &str, is_rated: bool) -> DingDaResult<bool> {
        self.store.update_rated(order_no, is_rated)
    }

    /// 新建订单。
    pub fn create(&self, order: &Order) -> DingDaResult<Order> {
        self.store.create_order(order)
    }

    /// 删除订单（归属校验）。
    pub fn delete(&self, owner_id: i64, order_id: i64) -> DingDaResult<bool> {
        self.store.delete_order(owner_id, order_id)
    }

    /// 批量删除（归属校验）。
    pub fn batch_delete(&self, owner_id: i64, order_ids: &[i64]) -> DingDaResult<u32> {
        self.store.batch_delete_orders(owner_id, order_ids)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_parsing_chinese_and_english() {
        assert_eq!(OrderStatus::from_str("pending"), OrderStatus::Pending);
        assert_eq!(OrderStatus::from_str("待发货"), OrderStatus::Pending);
        assert_eq!(OrderStatus::from_str("已付款"), OrderStatus::Paid);
        assert_eq!(OrderStatus::from_str("交易成功"), OrderStatus::Completed);
        assert_eq!(OrderStatus::from_str("已关闭"), OrderStatus::Closed);
        assert_eq!(OrderStatus::from_str("退款成功"), OrderStatus::Refunded);
        assert_eq!(OrderStatus::from_str("weird"), OrderStatus::Unknown);
    }

    #[test]
    fn pending_ship_detection() {
        assert!(OrderStatus::Pending.is_pending_ship());
        assert!(OrderStatus::Paid.is_pending_ship());
        assert!(!OrderStatus::Shipped.is_pending_ship());
        assert!(!OrderStatus::Closed.is_pending_ship());
    }

    #[test]
    fn delivery_content_truncation() {
        let long = "卡".repeat(2500);
        let normalized = Order::normalize_delivery_content(&long);
        assert!(normalized.chars().count() <= DELIVERY_CONTENT_MAX);
        assert!(normalized.ends_with("..."));
        let short = "卡密123";
        assert_eq!(Order::normalize_delivery_content(short), short);
    }

    #[test]
    fn delivery_method_roundtrip() {
        assert_eq!(DeliveryMethod::from_str("auto"), DeliveryMethod::Auto);
        assert_eq!(
            DeliveryMethod::from_str("scheduled"),
            DeliveryMethod::Scheduled
        );
        assert_eq!(DeliveryMethod::from_str("manual"), DeliveryMethod::Manual);
        assert_eq!(DeliveryMethod::from_str("x"), DeliveryMethod::Manual);
    }

    #[test]
    fn delivery_info_update_normalizes_content() {
        let long = "卡".repeat(2500);
        let mut update = DeliveryInfoUpdate {
            status: OrderStatus::Shipped,
            delivery_method: DeliveryMethod::Auto,
            delivery_content: Some(long),
            buyer_fish_nick: None,
        };
        if let Some(content) = &update.delivery_content {
            update.delivery_content = Some(Order::normalize_delivery_content(content));
        }
        assert!(
            update
                .delivery_content
                .as_ref()
                .expect("content")
                .chars()
                .count()
                <= DELIVERY_CONTENT_MAX
        );
    }
}
