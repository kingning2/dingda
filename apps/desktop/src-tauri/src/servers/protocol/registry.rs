//! 平台注册表 — 能力层与协议层的统一入口。
//!
//! 职责：
//! - 列出全部已知平台（[`ChannelKind`] 与 [`builtin_descriptors`] 对齐）；
//! - 查询平台能力（前端动态路由数据源）；
//! - 协议实现工厂的扩展点（新平台实现 [`ChannelProtocol`] 后在此登记）。
//!
//! 接入新平台三步：
//! 1. `protocol::ChannelKind` 加枚举值；
//! 2. `capabilities::builtin_descriptors` 声明能力清单；
//! 3. 实现 `ChannelProtocol` 并注册进 `ChannelDispatcher`（工厂登记见下）。

use std::collections::HashMap;
use std::sync::Arc;

use crate::servers::protocol::capabilities::{
    builtin_descriptors, PlatformCapabilities, PlatformDescriptor,
};
use crate::servers::protocol::{ChannelKind, ChannelProtocol};

/// 平台描述（含能力清单）— 前端动态路由数据源。
pub struct PlatformInfo {
    pub kind: ChannelKind,
    pub name: String,
    pub capabilities: PlatformCapabilities,
}

/// 平台注册表 — 只读查询入口（协议实例由 Dispatcher 持有）。
#[derive(Clone, Default)]
pub struct PlatformRegistry {
    /// kind → 协议实现（可选：未实现平台为空）。
    protocols: HashMap<ChannelKind, Arc<dyn ChannelProtocol>>,
}

impl PlatformRegistry {
    pub fn new() -> Self {
        Self {
            protocols: HashMap::new(),
        }
    }

    /// 登记协议实现（新平台扩展点）。
    pub fn register(&mut self, protocol: Arc<dyn ChannelProtocol>) {
        self.protocols.insert(protocol.kind(), protocol);
    }

    /// 取平台协议实现；未实现返回 `None`。
    pub fn protocol(&self, kind: ChannelKind) -> Option<Arc<dyn ChannelProtocol>> {
        self.protocols.get(&kind).cloned()
    }

    /// 该平台协议是否已实现。
    pub fn is_implemented(&self, kind: ChannelKind) -> bool {
        self.protocols.contains_key(&kind)
    }

    /// 全部平台信息（内置描述 + 实现状态）。
    pub fn all_platforms(&self) -> Vec<PlatformInfo> {
        builtin_descriptors()
            .into_iter()
            .map(|descriptor| PlatformInfo {
                kind: ChannelKind::from_str(&descriptor.kind).unwrap_or(ChannelKind::Xianyu),
                name: descriptor.name,
                capabilities: descriptor.capabilities,
            })
            .collect()
    }

    /// 查询平台描述（前端动态路由）。
    pub fn descriptors(&self) -> Vec<PlatformDescriptor> {
        builtin_descriptors()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_platforms_align_with_capabilities() {
        let registry = PlatformRegistry::new();
        let platforms = registry.all_platforms();
        assert_eq!(platforms.len(), builtin_descriptors().len());
        assert!(!platforms.is_empty());
    }

    #[test]
    fn unimplemented_platform_has_no_protocol() {
        let registry = PlatformRegistry::new();
        assert!(registry.protocol(ChannelKind::Xiaohongshu).is_none());
    }

    #[test]
    fn descriptors_include_capability_lists() {
        let registry = PlatformRegistry::new();
        let descriptors = registry.descriptors();
        assert!(!descriptors.is_empty());
        #[cfg(platform_xianyu)]
        {
            let xianyu = descriptors
                .iter()
                .find(|d| d.kind == "xianyu")
                .expect("xianyu");
            assert!(xianyu
                .capabilities
                .has(crate::servers::protocol::capabilities::PlatformCapability::Coupon));
        }
    }
}
