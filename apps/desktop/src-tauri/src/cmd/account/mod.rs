//! 账号业务 IPC（CRUD / 扫码 / 登录探针）。

mod crud;
mod qr;

pub use crud::{
    account_create, account_delete, account_list, account_probe_login, account_set_status,
    account_update, AccountHandle,
};
pub use qr::{
    account_qr_cancel, account_qr_check, account_qr_start, AccountQrHandle, PostQrLoginHook,
};
