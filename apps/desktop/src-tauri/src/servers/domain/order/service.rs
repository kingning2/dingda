//! 订单服务测试 — 用内存 mock 覆盖 OrderStore 全部方法。

#[cfg(test)]
mod tests {
    use crate::contracts::DingDaResult;
    use crate::servers::domain::order::{
        DeliveryInfoUpdate, DeliveryMethod, Order, OrderService, OrderStatus, OrderStore,
    };
    use std::sync::Mutex;

    struct MockStore {
        orders: Mutex<Vec<Order>>,
    }

    fn sample_order(order_no: &str, owner: i64, status: OrderStatus) -> Order {
        Order {
            id: order_no.parse::<i64>().unwrap_or(1),
            owner_id: owner,
            order_no: order_no.to_string(),
            status,
            buyer_nick: "买家".to_string(),
            buyer_fish_nick: String::new(),
            buyer_id: "buyer-1".to_string(),
            chat_id: String::new(),
            item_id: "item-1".to_string(),
            item_title: "商品".to_string(),
            spec_name: String::new(),
            spec_value: String::new(),
            quantity: 1,
            amount: 100.0,
            account_id: "acc-1".to_string(),
            account_name: "账号".to_string(),
            is_bargain: false,
            is_rated: false,
            is_red_flower: false,
            delivery_method: None,
            delivery_content: String::new(),
            delivery_fail_reason: String::new(),
            placed_at: None,
        }
    }

    impl MockStore {
        fn new(orders: Vec<Order>) -> Self {
            Self {
                orders: Mutex::new(orders),
            }
        }
    }

    impl OrderStore for MockStore {
        fn get_order(&self, order_no: &str) -> DingDaResult<Option<Order>> {
            Ok(self
                .orders
                .lock()
                .expect("lock")
                .iter()
                .find(|o| o.order_no == order_no)
                .cloned())
        }
        fn get_order_by_no(&self, owner_id: i64, order_no: &str) -> DingDaResult<Option<Order>> {
            Ok(self
                .orders
                .lock()
                .expect("lock")
                .iter()
                .find(|o| o.owner_id == owner_id && o.order_no == order_no)
                .cloned())
        }
        fn get_pending_order_by_buyer(
            &self,
            owner_id: i64,
            account_id: &str,
            buyer_id: &str,
            _item_id: Option<&str>,
        ) -> DingDaResult<Option<Order>> {
            Ok(self
                .orders
                .lock()
                .expect("lock")
                .iter()
                .find(|o| {
                    o.owner_id == owner_id
                        && o.account_id == account_id
                        && o.buyer_id == buyer_id
                        && o.status.is_pending_ship()
                })
                .cloned())
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
            let list: Vec<Order> = self
                .orders
                .lock()
                .expect("lock")
                .iter()
                .filter(|o| {
                    o.owner_id == owner_id
                        && status.map(|s| o.status == s).unwrap_or(true)
                        && buyer_id.is_none_or(|b| o.buyer_id == b)
                        && (keyword.is_empty() || o.order_no.contains(keyword))
                })
                .cloned()
                .collect();
            let total = list.len() as u32;
            Ok((list, total))
        }
        fn update_status(&self, order_no: &str, status: OrderStatus) -> DingDaResult<bool> {
            let mut list = self.orders.lock().expect("lock");
            let Some(order) = list.iter_mut().find(|o| o.order_no == order_no) else {
                return Ok(false);
            };
            order.status = status;
            Ok(true)
        }
        fn update_chat_id(&self, order_no: &str, chat_id: &str) -> DingDaResult<bool> {
            let mut list = self.orders.lock().expect("lock");
            let Some(order) = list.iter_mut().find(|o| o.order_no == order_no) else {
                return Ok(false);
            };
            order.chat_id = chat_id.to_string();
            Ok(true)
        }
        fn update_delivery_info(
            &self,
            order_no: &str,
            update: &DeliveryInfoUpdate,
        ) -> DingDaResult<bool> {
            let mut list = self.orders.lock().expect("lock");
            let Some(order) = list.iter_mut().find(|o| o.order_no == order_no) else {
                return Ok(false);
            };
            order.status = update.status;
            order.delivery_method = Some(update.delivery_method);
            order.delivery_content = update.delivery_content.clone().unwrap_or_default();
            order.delivery_fail_reason.clear();
            if let Some(nick) = &update.buyer_fish_nick {
                order.buyer_fish_nick = nick.clone();
            }
            Ok(true)
        }
        fn update_delivery_fail_reason(&self, order_no: &str, reason: &str) -> DingDaResult<bool> {
            let mut list = self.orders.lock().expect("lock");
            let Some(order) = list.iter_mut().find(|o| o.order_no == order_no) else {
                return Ok(false);
            };
            order.delivery_fail_reason = reason.to_string();
            Ok(true)
        }
        fn update_rated(&self, order_no: &str, is_rated: bool) -> DingDaResult<bool> {
            let mut list = self.orders.lock().expect("lock");
            let Some(order) = list.iter_mut().find(|o| o.order_no == order_no) else {
                return Ok(false);
            };
            order.is_rated = is_rated;
            Ok(true)
        }
        fn create_order(&self, order: &Order) -> DingDaResult<Order> {
            let mut order = order.clone();
            order.id = (self.orders.lock().expect("lock").len() + 1) as i64;
            self.orders.lock().expect("lock").push(order.clone());
            Ok(order)
        }
        fn delete_order(&self, owner_id: i64, order_id: i64) -> DingDaResult<bool> {
            let mut list = self.orders.lock().expect("lock");
            let before = list.len();
            list.retain(|o| !(o.owner_id == owner_id && o.id == order_id));
            Ok(list.len() < before)
        }
        fn batch_delete_orders(&self, owner_id: i64, order_ids: &[i64]) -> DingDaResult<u32> {
            let mut list = self.orders.lock().expect("lock");
            let before = list.len();
            list.retain(|o| !(o.owner_id == owner_id && order_ids.contains(&o.id)));
            Ok((before - list.len()) as u32)
        }
    }

    #[test]
    fn get_by_no_respects_ownership() {
        let store = MockStore::new(vec![
            sample_order("o-1", 1, OrderStatus::Pending),
            sample_order("o-2", 2, OrderStatus::Paid),
        ]);
        let service = OrderService::new(&store);
        assert!(service.get_order_by_no(1, "o-1").expect("get").is_some());
        assert!(service.get_order_by_no(2, "o-1").expect("get").is_none());
    }

    #[test]
    fn pending_order_by_buyer_only_matches_pending() {
        let store = MockStore::new(vec![
            sample_order("o-1", 1, OrderStatus::Paid),
            sample_order("o-2", 1, OrderStatus::Shipped),
        ]);
        let service = OrderService::new(&store);
        let pending = service
            .pending_order_by_buyer(1, "acc-1", "buyer-1", None)
            .expect("query")
            .expect("found");
        assert_eq!(pending.order_no, "o-1");
    }

    #[test]
    fn list_filters_by_status_and_keyword() {
        let store = MockStore::new(vec![
            sample_order("o-1", 1, OrderStatus::Paid),
            sample_order("o-2", 1, OrderStatus::Shipped),
            sample_order("o-3", 2, OrderStatus::Paid),
        ]);
        let service = OrderService::new(&store);
        let (list, total) = service
            .list(1, 1, 20, Some(OrderStatus::Paid), "", None)
            .expect("list");
        assert_eq!(total, 1);
        assert_eq!(list[0].order_no, "o-1");
    }

    #[test]
    fn list_filters_by_buyer() {
        let store = MockStore::new(vec![
            sample_order("o-1", 1, OrderStatus::Paid),
            sample_order("o-2", 1, OrderStatus::Shipped),
        ]);
        let service = OrderService::new(&store);
        let (list, total) = service
            .list(1, 1, 20, None, "", Some("buyer-1"))
            .expect("list");
        assert_eq!(total, 2);
        assert!(list.iter().all(|order| order.buyer_id == "buyer-1"));
        let (empty, empty_total) = service
            .list(1, 1, 20, None, "", Some("buyer-2"))
            .expect("list");
        assert_eq!(empty_total, 0);
        assert!(empty.is_empty());
    }

    #[test]
    fn update_delivery_info_clears_fail_reason() {
        let mut order = sample_order("o-1", 1, OrderStatus::Pending);
        order.delivery_fail_reason = "旧原因".to_string();
        let store = MockStore::new(vec![order]);
        let service = OrderService::new(&store);
        service
            .update_delivery_info(
                "o-1",
                DeliveryInfoUpdate {
                    status: OrderStatus::Shipped,
                    delivery_method: DeliveryMethod::Auto,
                    delivery_content: Some("卡密".to_string()),
                    buyer_fish_nick: Some("昵称".to_string()),
                },
            )
            .expect("update");
        let order = service.get_order("o-1").expect("get").expect("found");
        assert_eq!(order.status, OrderStatus::Shipped);
        assert_eq!(order.delivery_content, "卡密");
        assert!(order.delivery_fail_reason.is_empty());
        assert_eq!(order.buyer_fish_nick, "昵称");
    }

    #[test]
    fn update_chat_id_rejects_empty() {
        let store = MockStore::new(vec![sample_order("o-1", 1, OrderStatus::Pending)]);
        let service = OrderService::new(&store);
        assert!(service.update_chat_id("o-1", "  ").is_err());
        assert!(service.update_chat_id("o-1", "chat-9").is_ok());
    }

    #[test]
    fn rated_and_status_updates() {
        let store = MockStore::new(vec![sample_order("o-1", 1, OrderStatus::Pending)]);
        let service = OrderService::new(&store);
        service.update_rated("o-1", true).expect("rated");
        service
            .update_status("o-1", OrderStatus::Completed)
            .expect("status");
        let order = service.get_order("o-1").expect("get").expect("found");
        assert!(order.is_rated);
        assert_eq!(order.status, OrderStatus::Completed);
    }

    #[test]
    fn delete_and_batch_delete_respect_ownership() {
        let store = MockStore::new(vec![
            sample_order("1", 1, OrderStatus::Pending),
            sample_order("2", 1, OrderStatus::Pending),
            sample_order("3", 2, OrderStatus::Pending),
        ]);
        let service = OrderService::new(&store);
        assert!(!service.delete(2, 1).expect("delete")); // owner 2 无权删 owner1 的 id=1
        assert!(service.delete(1, 1).expect("delete"));
        let count = service.batch_delete(1, &[2, 3]).expect("batch");
        assert_eq!(count, 1); // 仅 id=2（owner1）；id=3 属 owner2
        assert_eq!(service.list(1, 1, 20, None, "", None).expect("list").1, 0);
    }
}
