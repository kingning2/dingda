//! 商品管理 — 商品模型 + 分页查询服务。
//!
//! 对齐 Python 版 `xy_catalog_items` 模型与商品管理业务：
//! - 商品（item_id 唯一 / 标题 / 价格 / 擦亮 / 多规格 / 卡券关联）；
//! - 分页查询（关键词 / 账号筛选）；
//! - 商品详情（AI 提示词 / 默认回复 / 卡券配置状态）。

use crate::contracts::DingDaResult;
use serde::{Deserialize, Serialize};

/// 商品（对齐 `xy_catalog_items` 核心字段）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Item {
    pub id: i64,
    pub owner_id: i64,
    /// 账号标识。
    pub account_id: String,
    /// 平台商品 ID（唯一）。
    pub item_id: String,
    pub title: String,
    pub price: f64,
    pub desc: String,
    /// 是否已擦亮。
    pub is_polished: bool,
    /// 是否多规格。
    pub is_multi_spec: bool,
    /// 是否多数量发货。
    pub multi_quantity_delivery: bool,
    /// AI 提示词（商品特殊说明）。
    pub ai_prompt: String,
    /// 是否配置了发货卡券。
    pub has_card: bool,
    /// 是否配置了默认回复。
    pub has_default_reply: bool,
    pub created_at: Option<String>,
}

/// 商品查询条件。
#[derive(Debug, Clone, Default)]
pub struct ItemQuery {
    pub page: u32,
    pub page_size: u32,
    /// 关键词（商品 ID / 标题）。
    pub keyword: String,
    pub account_id: String,
    /// 是否已擦亮。
    pub is_polished: Option<bool>,
    /// 是否多规格。
    pub is_multi_spec: Option<bool>,
}

/// 商品存储 Port。
pub trait ItemStore: Send + Sync {
    /// 分页查询商品。
    fn list_items(&self, owner_id: i64, query: &ItemQuery) -> DingDaResult<(Vec<Item>, u32)>;

    /// 按商品 ID 查询。
    fn get_item(&self, owner_id: i64, item_id: &str) -> DingDaResult<Option<Item>>;

    /// 更新商品（AI 提示词等）。
    fn update_item(&self, item: &Item) -> DingDaResult<()>;

    /// 新建或更新商品（平台同步入库；保留已有本地配置字段）。
    fn upsert_item(&self, item: &Item) -> DingDaResult<()>;
}

/// 商品服务。
pub struct ItemService<'a> {
    store: &'a dyn ItemStore,
}

impl<'a> ItemService<'a> {
    pub fn new(store: &'a dyn ItemStore) -> Self {
        Self { store }
    }

    /// 分页查询。
    pub fn list(&self, owner_id: i64, query: &ItemQuery) -> DingDaResult<(Vec<Item>, u32)> {
        self.store.list_items(owner_id, query)
    }

    /// 按商品 ID 查询。
    pub fn get(&self, owner_id: i64, item_id: &str) -> DingDaResult<Option<Item>> {
        self.store.get_item(owner_id, item_id)
    }

    /// 更新商品（AI 提示词）。
    pub fn update(
        &self,
        owner_id: i64,
        item_id: &str,
        apply: impl FnOnce(&mut Item),
    ) -> DingDaResult<()> {
        let Some(mut item) = self.store.get_item(owner_id, item_id)? else {
            return Err("商品不存在或无权限".to_string().into());
        };
        apply(&mut item);
        self.store.update_item(&item)
    }

    /// 新建或更新商品（平台同步）。
    pub fn upsert(&self, item: &Item) -> DingDaResult<()> {
        self.store.upsert_item(item)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    struct MockStore {
        items: Mutex<Vec<Item>>,
    }

    impl MockStore {
        fn new(items: Vec<Item>) -> Self {
            Self {
                items: Mutex::new(items),
            }
        }
    }

    impl ItemStore for MockStore {
        fn list_items(&self, owner_id: i64, query: &ItemQuery) -> DingDaResult<(Vec<Item>, u32)> {
            let list: Vec<Item> = self
                .items
                .lock()
                .expect("lock")
                .iter()
                .filter(|item| {
                    item.owner_id == owner_id
                        && (query.account_id.is_empty() || item.account_id == query.account_id)
                        && (query.keyword.is_empty()
                            || item.item_id.contains(&query.keyword)
                            || item.title.contains(&query.keyword))
                        && query
                            .is_polished
                            .map(|p| item.is_polished == p)
                            .unwrap_or(true)
                        && query
                            .is_multi_spec
                            .map(|m| item.is_multi_spec == m)
                            .unwrap_or(true)
                })
                .cloned()
                .collect();
            let total = list.len() as u32;
            Ok((list, total))
        }
        fn get_item(&self, owner_id: i64, item_id: &str) -> DingDaResult<Option<Item>> {
            Ok(self
                .items
                .lock()
                .expect("lock")
                .iter()
                .find(|item| item.owner_id == owner_id && item.item_id == item_id)
                .cloned())
        }
        fn update_item(&self, item: &Item) -> DingDaResult<()> {
            let mut list = self.items.lock().expect("lock");
            if let Some(existing) = list.iter_mut().find(|i| i.id == item.id) {
                *existing = item.clone();
            }
            Ok(())
        }
        fn upsert_item(&self, item: &Item) -> DingDaResult<()> {
            let mut list = self.items.lock().expect("lock");
            if let Some(existing) = list
                .iter_mut()
                .find(|i| i.owner_id == item.owner_id && i.item_id == item.item_id)
            {
                existing.title = item.title.clone();
                existing.price = item.price;
                existing.desc = item.desc.clone();
                existing.account_id = item.account_id.clone();
                return Ok(());
            }
            let mut item = item.clone();
            if item.id == 0 {
                item.id = (list.len() + 1) as i64;
            }
            list.push(item);
            Ok(())
        }
    }

    fn item(item_id: &str, owner: i64, title: &str) -> Item {
        Item {
            id: 1,
            owner_id: owner,
            account_id: "acc-1".to_string(),
            item_id: item_id.to_string(),
            title: title.to_string(),
            price: 100.0,
            desc: String::new(),
            is_polished: false,
            is_multi_spec: false,
            multi_quantity_delivery: false,
            ai_prompt: String::new(),
            has_card: false,
            has_default_reply: false,
            created_at: None,
        }
    }

    #[test]
    fn list_filters_by_keyword_and_owner() {
        let store = MockStore::new(vec![
            item("item-1", 1, "二手手机"),
            item("item-2", 1, "全新耳机"),
            item("item-3", 2, "二手手机"),
        ]);
        let service = ItemService::new(&store);
        let query = ItemQuery {
            page: 1,
            page_size: 20,
            keyword: "手机".to_string(),
            account_id: String::new(),
            is_polished: None,
            is_multi_spec: None,
        };
        let (list, total) = service.list(1, &query).expect("list");
        assert_eq!(total, 1);
        assert_eq!(list[0].item_id, "item-1");
    }

    #[test]
    fn get_respects_ownership() {
        let store = MockStore::new(vec![item("item-1", 1, "x")]);
        let service = ItemService::new(&store);
        assert!(service.get(1, "item-1").expect("get").is_some());
        assert!(service.get(2, "item-1").expect("get").is_none());
    }

    #[test]
    fn update_applies_ai_prompt() {
        let store = MockStore::new(vec![item("item-1", 1, "x")]);
        let service = ItemService::new(&store);
        service
            .update(1, "item-1", |item| item.ai_prompt = "不议价".to_string())
            .expect("update");
        let updated = service.get(1, "item-1").expect("get").expect("found");
        assert_eq!(updated.ai_prompt, "不议价");
    }

    #[test]
    fn update_requires_ownership() {
        let store = MockStore::new(vec![item("item-1", 1, "x")]);
        let service = ItemService::new(&store);
        assert!(service.update(2, "item-1", |_| {}).is_err());
    }
}
