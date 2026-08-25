//! 编译期平台壳层。
//!
//! - [`core`] — 两站共用 IPC（账号 CRUD / 扫码登录）
//! - [`discovery`] — 跨站选品：闲鱼（需求）× 1688（货源）比价发现循环
//! - [`xianyu`] — 闲鱼（`platform_xianyu`）：WS 连接、商品、订单等
//! - [`ali1688`] — 1688（`platform_ali1688`）：账号库 + 扫码 Handle，不注册闲鱼 WS
//! - [`ipc`] — IPC 注册链（共享 + core + 各站 `platform_ipc_step_*`）
//! - [`runtime`] — 平台运行时装配（风控 / 渠道协议）
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub mod core;
pub mod discovery;
pub mod ipc;
pub mod runtime;

#[cfg(platform_ali1688)]
pub mod ali1688;
#[cfg(platform_xianyu)]
pub mod xianyu;
