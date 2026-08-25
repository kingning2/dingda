//! 账号服务 — 归属校验 + CRUD + 状态操作。
//!
//! 对齐 Python 版账号管理业务：
//! - 账号归属校验（owner_id + account_id 唯一）；
//! - 新建需 Cookie 必备、account_id 唯一；
//! - 禁用/启用状态切换；
//! - 代理与自动化配置更新。

use super::{AccountStatus, AccountUpdate, XianyuAccount};
use crate::contracts::DingDaResult;
use thiserror::Error;

/// 账号服务错误。
#[derive(Debug, Error)]
pub enum AccountServiceError {
    #[error("validation failed: {0}")]
    Validation(String),
    #[error("store error: {0}")]
    Store(String),
    #[error("not found: account {0}")]
    NotFound(String),
    #[error("conflict: {0}")]
    Conflict(String),
}

/// 账号存储 Port。
pub trait AccountStore: Send + Sync {
    /// 按 owner + account_id 查询（归属校验）。
    fn get_account(&self, owner_id: i64, account_id: &str) -> DingDaResult<Option<XianyuAccount>>;

    /// 查询用户全部账号。
    fn list_accounts(&self, owner_id: i64) -> DingDaResult<Vec<XianyuAccount>>;

    /// 新建账号（返回带 id 的账号）。
    fn create_account(&self, account: &XianyuAccount) -> DingDaResult<XianyuAccount>;

    /// 更新账号。
    fn update_account(&self, account: &XianyuAccount) -> DingDaResult<()>;

    /// 删除账号。
    fn delete_account(&self, owner_id: i64, account_id: &str) -> DingDaResult<()>;

    /// 按 account_id 全局查询（唯一性校验）。
    fn find_by_account_id(&self, account_id: &str) -> DingDaResult<Option<XianyuAccount>>;
}

/// 账号服务。
pub struct AccountService<'a> {
    store: &'a dyn AccountStore,
}

impl<'a> AccountService<'a> {
    pub fn new(store: &'a dyn AccountStore) -> Self {
        Self { store }
    }

    /// 校验新建入参。
    pub fn validate_new(
        &self,
        owner_id: i64,
        account: &XianyuAccount,
    ) -> Result<(), AccountServiceError> {
        if account.account_id.trim().is_empty() {
            return Err(AccountServiceError::Validation(
                "账号标识不能为空".to_string(),
            ));
        }
        if !account.has_cookie() {
            return Err(AccountServiceError::Validation(
                "账号 Cookie 不能为空".to_string(),
            ));
        }
        // account_id 全局唯一。
        if let Some(existing) = self
            .store
            .find_by_account_id(&account.account_id)
            .map_err(|e| AccountServiceError::Store(e.to_string()))?
        {
            if existing.owner_id != owner_id {
                return Err(AccountServiceError::Conflict(format!(
                    "账号 {} 已被其他用户使用",
                    account.account_id
                )));
            }
            return Err(AccountServiceError::Conflict(format!(
                "账号 {} 已存在",
                account.account_id
            )));
        }
        Ok(())
    }

    /// 新建账号。
    pub fn create(
        &self,
        owner_id: i64,
        account: &XianyuAccount,
    ) -> Result<XianyuAccount, AccountServiceError> {
        self.validate_new(owner_id, account)?;
        self.store
            .create_account(account)
            .map_err(|e| AccountServiceError::Store(e.to_string()))
    }

    /// 更新账号（归属校验 + 部分字段）。
    pub fn update(
        &self,
        owner_id: i64,
        account_id: &str,
        patch: &AccountUpdate,
    ) -> Result<XianyuAccount, AccountServiceError> {
        let Some(mut account) = self
            .store
            .get_account(owner_id, account_id)
            .map_err(|e| AccountServiceError::Store(e.to_string()))?
        else {
            return Err(AccountServiceError::NotFound(account_id.to_string()));
        };

        if let Some(display_name) = &patch.display_name {
            account.display_name = display_name.clone();
        }
        if let Some(avatar_url) = &patch.avatar_url {
            account.avatar_url = avatar_url.clone();
        }
        if let Some(remark) = &patch.remark {
            account.remark = remark.clone();
        }
        if let Some(login_id) = &patch.login_id {
            account.login_id = login_id.clone();
        }
        if let Some(login_password) = &patch.login_password {
            account.login_password = login_password.clone();
        }
        if let Some(status) = patch.status {
            account.status = status;
        }
        if let Some(cookie) = &patch.cookie {
            account.cookie = cookie.clone();
        }
        if let Some(cookie_1688) = &patch.cookie_1688 {
            account.cookie_1688 = cookie_1688.clone();
        }
        if let Some(unb) = &patch.unb {
            account.unb = unb.clone();
        }
        if let Some(platform) = &patch.platform {
            account.platform = platform.clone();
        }
        if let Some(login_method) = patch.login_method {
            account.login_method = login_method;
        }
        if let Some(last_login_at) = &patch.last_login_at {
            account.last_login_at = Some(last_login_at.clone());
        }
        if let Some(proxy) = &patch.proxy {
            account.proxy = proxy.clone();
        }
        if let Some(automation) = &patch.automation {
            account.automation = automation.clone();
        }
        if let Some(delivery_guard) = &patch.delivery_guard {
            account.delivery_guard = delivery_guard.clone();
        }
        if let Some(pause) = patch.pause_duration_minutes {
            account.pause_duration_minutes = pause;
        }

        self.store
            .update_account(&account)
            .map_err(|e| AccountServiceError::Store(e.to_string()))?;
        Ok(account)
    }

    /// 切换启用状态。
    pub fn set_status(
        &self,
        owner_id: i64,
        account_id: &str,
        status: AccountStatus,
    ) -> Result<(), AccountServiceError> {
        let mut account = self
            .store
            .get_account(owner_id, account_id)
            .map_err(|e| AccountServiceError::Store(e.to_string()))?
            .ok_or_else(|| AccountServiceError::NotFound(account_id.to_string()))?;
        account.status = status;
        self.store
            .update_account(&account)
            .map_err(|e| AccountServiceError::Store(e.to_string()))
    }

    /// 删除账号。
    pub fn delete(&self, owner_id: i64, account_id: &str) -> Result<(), AccountServiceError> {
        if self
            .store
            .get_account(owner_id, account_id)
            .map_err(|e| AccountServiceError::Store(e.to_string()))?
            .is_none()
        {
            return Err(AccountServiceError::NotFound(account_id.to_string()));
        }
        self.store
            .delete_account(owner_id, account_id)
            .map_err(|e| AccountServiceError::Store(e.to_string()))
    }

    /// 列表。
    pub fn list(&self, owner_id: i64) -> Result<Vec<XianyuAccount>, AccountServiceError> {
        self.store
            .list_accounts(owner_id)
            .map_err(|e| AccountServiceError::Store(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::domain::account::{AccountAutomation, LoginMethod};
    use std::sync::Mutex;

    struct MockStore {
        accounts: Mutex<Vec<XianyuAccount>>,
    }

    impl MockStore {
        fn new(accounts: Vec<XianyuAccount>) -> Self {
            Self {
                accounts: Mutex::new(accounts),
            }
        }
    }

    impl AccountStore for MockStore {
        fn get_account(
            &self,
            owner_id: i64,
            account_id: &str,
        ) -> DingDaResult<Option<XianyuAccount>> {
            Ok(self
                .accounts
                .lock()
                .expect("lock")
                .iter()
                .find(|a| a.owner_id == owner_id && a.account_id == account_id)
                .cloned())
        }
        fn list_accounts(&self, owner_id: i64) -> DingDaResult<Vec<XianyuAccount>> {
            Ok(self
                .accounts
                .lock()
                .expect("lock")
                .iter()
                .filter(|a| a.owner_id == owner_id)
                .cloned()
                .collect())
        }
        fn create_account(&self, account: &XianyuAccount) -> DingDaResult<XianyuAccount> {
            let mut account = account.clone();
            account.id = (self.accounts.lock().expect("lock").len() + 1) as i64;
            self.accounts.lock().expect("lock").push(account.clone());
            Ok(account)
        }
        fn update_account(&self, account: &XianyuAccount) -> DingDaResult<()> {
            let mut list = self.accounts.lock().expect("lock");
            if let Some(existing) = list.iter_mut().find(|a| a.id == account.id) {
                *existing = account.clone();
            }
            Ok(())
        }
        fn delete_account(&self, owner_id: i64, account_id: &str) -> DingDaResult<()> {
            self.accounts
                .lock()
                .expect("lock")
                .retain(|a| !(a.owner_id == owner_id && a.account_id == account_id));
            Ok(())
        }
        fn find_by_account_id(&self, account_id: &str) -> DingDaResult<Option<XianyuAccount>> {
            Ok(self
                .accounts
                .lock()
                .expect("lock")
                .iter()
                .find(|a| a.account_id == account_id)
                .cloned())
        }
    }

    fn account(owner: i64, account_id: &str, cookie: &str) -> XianyuAccount {
        XianyuAccount {
            id: 0,
            owner_id: owner,
            account_id: account_id.to_string(),
            display_name: "账号".to_string(),
            avatar_url: String::new(),
            login_id: String::new(),
            login_password: String::new(),
            unb: String::new(),
            cookie: cookie.to_string(),
            cookie_1688: String::new(),
            platform: "xianyu".to_string(),
            login_method: LoginMethod::Qr,
            status: AccountStatus::Active,
            remark: String::new(),
            pause_duration_minutes: 10,
            last_login_at: None,
            last_refresh_at: None,
            proxy: Default::default(),
            automation: AccountAutomation::default(),
            delivery_guard: Default::default(),
        }
    }

    #[test]
    fn create_validates_cookie() {
        let store = MockStore::new(vec![]);
        let service = AccountService::new(&store);
        assert!(matches!(
            service.create(1, &account(1, "acc-1", "")),
            Err(AccountServiceError::Validation(_))
        ));
        assert!(service.create(1, &account(1, "acc-1", "c=1")).is_ok());
    }

    #[test]
    fn create_rejects_duplicate_account_id() {
        let store = MockStore::new(vec![account(1, "acc-1", "c=1")]);
        let service = AccountService::new(&store);
        // 同 owner 重复 → conflict。
        assert!(matches!(
            service.create(1, &account(1, "acc-1", "c=2")),
            Err(AccountServiceError::Conflict(_))
        ));
        // 不同 owner 占用 → conflict。
        assert!(matches!(
            service.create(2, &account(2, "acc-1", "c=2")),
            Err(AccountServiceError::Conflict(_))
        ));
    }

    #[test]
    fn update_partial_fields() {
        let store = MockStore::new(vec![account(1, "acc-1", "c=1")]);
        let service = AccountService::new(&store);
        let patch = AccountUpdate {
            display_name: Some("新名字".to_string()),
            automation: Some(AccountAutomation {
                auto_confirm: true,
                ..Default::default()
            }),
            ..Default::default()
        };
        let updated = service.update(1, "acc-1", &patch).expect("update");
        assert_eq!(updated.display_name, "新名字");
        assert!(updated.automation.auto_confirm);
    }

    #[test]
    fn update_requires_ownership() {
        let store = MockStore::new(vec![account(1, "acc-1", "c=1")]);
        let service = AccountService::new(&store);
        assert!(matches!(
            service.update(2, "acc-1", &AccountUpdate::default()),
            Err(AccountServiceError::NotFound(_))
        ));
    }

    #[test]
    fn set_status_toggles() {
        let store = MockStore::new(vec![account(1, "acc-1", "c=1")]);
        let service = AccountService::new(&store);
        service
            .set_status(1, "acc-1", AccountStatus::Disabled)
            .expect("set");
        let list = service.list(1).expect("list");
        assert_eq!(list[0].status, AccountStatus::Disabled);
    }

    #[test]
    fn delete_requires_ownership() {
        let store = MockStore::new(vec![account(1, "acc-1", "c=1")]);
        let service = AccountService::new(&store);
        assert!(matches!(
            service.delete(2, "acc-1"),
            Err(AccountServiceError::NotFound(_))
        ));
        assert!(service.delete(1, "acc-1").is_ok());
    }
}
