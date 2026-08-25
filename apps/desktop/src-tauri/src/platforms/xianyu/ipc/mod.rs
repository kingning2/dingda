//! 闲鱼业务 IPC commands。
//!
//! 账号 CRUD / 扫码登录为两站共用，已上移到 `crate::platforms::core`；
//! 本模块仅保留闲鱼专属命令（连接 / 商品 / 订单 / 风控 / 仪表盘 / 用户设置 / 渠道历史 / 渠道扫码）。
//!
//! 精简说明：发布 / 卡券 / 黑名单 / 关键词 / 消息过滤 / 通知 / 反馈 / 评价等
//! 子页已下线，对应命令壳一并删除。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub mod account_connection;
pub mod chain;
pub mod chat;
pub mod dashboard;
pub mod item;
pub mod monitor;
pub mod order;
pub mod risk;
pub mod search;
pub mod setting;

pub use account_connection::{
    account_connect, account_connection_state, account_cookie_renew, account_disconnect,
};
pub use chat::{
    channel_fetch_history, channel_product_headinfo, channel_qr_cancel, channel_qr_check,
    channel_qr_start,
};
pub use dashboard::dashboard_stats;
pub use item::{item_detail_fetch, item_get, item_list, item_sync, item_update};
pub use monitor::{
    monitor_generate_keywords, monitor_result_list, monitor_run_get, monitor_run_list,
    monitor_stats, monitor_task_delete, monitor_task_list, monitor_task_pause_schedule,
    monitor_task_resume_schedule, monitor_task_run, monitor_task_save,
};
pub use order::{
    order_create, order_delete, order_get, order_list, order_update_delivery, order_update_status,
};
pub use risk::{
    risk_config_get, risk_config_set, risk_log_clear, risk_log_clear_processing, risk_log_list,
    risk_log_today_rate,
};
pub use search::xianyu_search;
pub use setting::{user_setting_get, user_setting_set};
