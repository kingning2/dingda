//! 渠道连接 / 会话 / 扫码 IPC。

mod state;

#[cfg(platform_xianyu)]
mod chat;
#[cfg(platform_xianyu)]
mod connection;

pub use state::{
    channel_connect, channel_disconnect, channel_send, channel_state_get, channel_state_set,
};

#[cfg(platform_xianyu)]
pub use chat::{
    channel_fetch_history, channel_product_headinfo, channel_qr_cancel, channel_qr_check,
    channel_qr_start,
};
#[cfg(platform_xianyu)]
pub use connection::{
    account_connect, account_connection_state, account_cookie_renew, account_disconnect,
    to_channel_account,
};

#[cfg(platform_xianyu)]
pub use connection::sync_account_profile;
