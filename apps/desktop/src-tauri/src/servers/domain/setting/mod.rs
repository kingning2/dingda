//! 用户设置 — 用户级键值配置存取。
//!
//! 对齐 Python 版 `/api/v1/user-settings` 的用户级设置语义（桌面单用户）。
//! 精简说明：个人设置聚合视图（重发货关键字 / 联系方式 / 卡密秘钥）已下线，
//! 仅保留通用键值读写。

use crate::contracts::DingDaResult;

/// 用户设置存储 Port。
pub trait UserSettingStore: Send + Sync {
    /// 读取单键值。
    fn get(&self, owner_id: i64, key: &str) -> DingDaResult<Option<String>>;

    /// 写入单键值（空值按删除处理）。
    fn set(&self, owner_id: i64, key: &str, value: &str) -> DingDaResult<()>;
}

/// 用户设置服务。
pub struct UserSettingService<'a> {
    store: &'a dyn UserSettingStore,
}

impl<'a> UserSettingService<'a> {
    pub fn new(store: &'a dyn UserSettingStore) -> Self {
        Self { store }
    }

    /// 读取单键值。
    pub fn get(&self, owner_id: i64, key: &str) -> DingDaResult<Option<String>> {
        self.store.get(owner_id, key)
    }

    /// 写入单键值（空值删除）。
    pub fn set(&self, owner_id: i64, key: &str, value: &str) -> DingDaResult<()> {
        if key.trim().is_empty() {
            return Err("设置键不能为空".to_string().into());
        }
        let value = value.trim();
        self.store.set(owner_id, key.trim(), value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Mutex;

    struct MockStore {
        map: Mutex<HashMap<(i64, String), String>>,
    }

    impl UserSettingStore for MockStore {
        fn get(&self, owner_id: i64, key: &str) -> DingDaResult<Option<String>> {
            Ok(self
                .map
                .lock()
                .expect("lock")
                .get(&(owner_id, key.to_string()))
                .cloned())
        }
        fn set(&self, owner_id: i64, key: &str, value: &str) -> DingDaResult<()> {
            let mut map = self.map.lock().expect("lock");
            if value.is_empty() {
                map.remove(&(owner_id, key.to_string()));
            } else {
                map.insert((owner_id, key.to_string()), value.to_string());
            }
            Ok(())
        }
    }

    #[test]
    fn set_and_get_roundtrip() {
        let store = MockStore {
            map: Mutex::new(HashMap::new()),
        };
        let service = UserSettingService::new(&store);
        service.set(1, "test.key", " 重新触发 ").expect("set");
        assert_eq!(
            service.get(1, "test.key").expect("get").as_deref(),
            Some("重新触发")
        );
        // 空值删除
        service.set(1, "test.key", "").expect("set");
        assert_eq!(service.get(1, "test.key").expect("get"), None);
    }

    #[test]
    fn set_rejects_empty_key() {
        let store = MockStore {
            map: Mutex::new(HashMap::new()),
        };
        let service = UserSettingService::new(&store);
        assert!(service.set(1, "  ", "value").is_err());
    }
}
