//! protocol crate — 渠道协议能力家族 **Service-Definition seam**。
//!
//! 职责：
//! - `protocol` — 渠道统一 `ChannelProtocol` trait + 入站消息归一化
//! - `dispatcher` — 多账号调度器（注册表 + 生命周期）
//! - `capabilities` — 平台能力清单（前端动态路由元数据）
//! - `registry` — 平台注册表（能力层 + 协议层统一入口）
//! - `compile` — 编译期渠道平台选择（`DINGDA_CHANNEL_PLATFORM` / `platform_*` cfg）
//!
//! 本 crate 是 **seam**：只定义契约与目录，**不含任何具体平台实现**。
//! 具体平台（`platform-xianyu` / `platform-ali1688`）作为 Provider 依赖本 crate，
//! 实现 [`protocol::ChannelProtocol`] 并注册进 [`dispatcher::ChannelDispatcher`]。
//!
//! ## 扩展点：接入新平台
//!
//! 1. `protocol::ChannelKind` 加枚举值；
//! 2. `capabilities::builtin_descriptors` 声明能力清单；
//! 3. 新建 Provider crate 实现 [`protocol::ChannelProtocol`]，在装配点注册进
//!    [`dispatcher::ChannelDispatcher`] / [`registry::PlatformRegistry`]。
//!
//! 设计约束：
//! - **不依赖 Tauri、不依赖具体平台、不依赖业务层**（`platform_*` cfg 由本 crate
//!   自己的 build.rs 注入，与 `tooling/build/channel_platform_cfg.rs` 共享）。
//! - 协议层不感知业务：不读库、不决策回复、不调 LLM。

pub mod capabilities;
pub mod compile;
pub mod dispatcher;
#[allow(clippy::module_inception)] // protocol::protocol 是渠道协议 seam 的核心模块名，保留
pub mod protocol;
pub mod registry;

pub use capabilities::{PlatformCapabilities, PlatformCapability, PlatformDescriptor};
pub use common::DingDaResult;
pub use compile::{
    active_kind, enabled_platform_ids, is_active, is_active_id, ACTIVE_PLATFORM, ENABLED_PLATFORMS,
};
pub use dispatcher::{ChannelDispatcher, ChannelProtocolFactory, DispatcherError};
pub use protocol::{
    ChannelAccount, ChannelError, ChannelInboundMessage, ChannelKind, ChannelProtocol,
    ConnectionState, ConversationSync, HistoryMessage, InboundListener,
};
pub use registry::{PlatformInfo, PlatformRegistry};
