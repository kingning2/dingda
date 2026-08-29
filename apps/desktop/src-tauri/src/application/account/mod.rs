//! 账号登录态探活用例（启动 / IPC 共用）。

mod session_probe;

pub use session_probe::{
    probe_account_session, probe_all_accounts_on_startup, AccountSessionProbeItem,
    AccountsSessionProbedPayload, ACCOUNTS_SESSION_PROBED_TOPIC,
};
