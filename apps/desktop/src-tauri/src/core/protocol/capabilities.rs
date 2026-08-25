//! 平台能力清单 — 前端动态路由的元数据源。
//!
//! 每个平台声明自己支持的能力；前端据此动态渲染路由。
//! 例：闲鱼有 `Coupon`（优惠券）板块，小红书/抖音没有 → 选择小红书时不渲染该路由。
//!
//! 约定：能力名小写、`_` 分隔，与前端路由 key / 契约字符串对齐。

use serde::{Deserialize, Serialize};

/// 平台能力枚举 — 新增能力在此扩展，并在对应平台描述中声明。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PlatformCapability {
    /// 在线聊天 / 会话收发
    Chat,
    /// 自动回复（关键词 / AI / 默认）
    AutoReply,
    /// 优惠券 / 卡券板块
    Coupon,
    /// 自动发货（虚拟商品 / 卡券）
    AutoDelivery,
    /// 商品发布
    ProductPublish,
    /// 商品采集 / 货源 / 分销
    Distribution,
    /// 订单管理
    Order,
    /// 评价 / 求小红花
    Rate,
    /// 商品监控
    ListingMonitor,
    /// 账号管理
    Account,
    /// 管理后台业务页（账号/商品/订单/卡券等子页面聚合，仅闲鱼实现）
    Manage,
}

impl PlatformCapability {
    /// 契约字符串（小写 snake_case，与前端路由 key 对齐）。
    pub fn as_str(&self) -> &'static str {
        match self {
            PlatformCapability::Chat => "chat",
            PlatformCapability::AutoReply => "auto_reply",
            PlatformCapability::Coupon => "coupon",
            PlatformCapability::AutoDelivery => "auto_delivery",
            PlatformCapability::ProductPublish => "product_publish",
            PlatformCapability::Distribution => "distribution",
            PlatformCapability::Order => "order",
            PlatformCapability::Rate => "rate",
            PlatformCapability::ListingMonitor => "listing_monitor",
            PlatformCapability::Account => "account",
            PlatformCapability::Manage => "manage",
        }
    }
}

/// 平台能力清单（某平台支持的完整能力集合）。
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PlatformCapabilities {
    pub capabilities: Vec<PlatformCapability>,
}

impl PlatformCapabilities {
    pub fn new(capabilities: Vec<PlatformCapability>) -> Self {
        Self { capabilities }
    }

    pub fn has(&self, capability: PlatformCapability) -> bool {
        self.capabilities.contains(&capability)
    }

    /// 序列化为契约字符串列表（前端直接消费）。
    pub fn as_strings(&self) -> Vec<String> {
        self.capabilities
            .iter()
            .map(|cap| cap.as_str().to_string())
            .collect()
    }
}

/// 平台描述 — 注册表项 + 动态路由元数据。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformDescriptor {
    /// 平台标识（小写，与 `ChannelKind::as_str` 对齐）。
    pub kind: String,
    /// 展示名称。
    pub name: String,
    /// 能力清单。
    pub capabilities: PlatformCapabilities,
}

/// 内置平台描述注册表 — 仅包含当前编译选定的平台（`platform_*` cfg）。
pub fn builtin_descriptors() -> Vec<PlatformDescriptor> {
    vec![
        #[cfg(platform_xianyu)]
        xianyu_descriptor(),
        #[cfg(platform_ali1688)]
        ali1688_descriptor(),
        #[cfg(platform_xiaohongshu)]
        xiaohongshu_descriptor(),
        #[cfg(platform_douyin)]
        douyin_descriptor(),
    ]
}

#[cfg(platform_xianyu)]
fn xianyu_descriptor() -> PlatformDescriptor {
    PlatformDescriptor {
        kind: "xianyu".to_string(),
        name: "闲鱼".to_string(),
        capabilities: PlatformCapabilities::new(vec![
            PlatformCapability::Chat,
            PlatformCapability::AutoReply,
            PlatformCapability::Coupon,
            PlatformCapability::AutoDelivery,
            PlatformCapability::ProductPublish,
            PlatformCapability::Distribution,
            PlatformCapability::Order,
            PlatformCapability::Rate,
            PlatformCapability::ListingMonitor,
            PlatformCapability::Account,
            PlatformCapability::Manage,
        ]),
    }
}

#[cfg(platform_ali1688)]
fn ali1688_descriptor() -> PlatformDescriptor {
    PlatformDescriptor {
        kind: "ali1688".to_string(),
        name: "1688".to_string(),
        capabilities: PlatformCapabilities::new(vec![
            PlatformCapability::Account,
            PlatformCapability::Manage,
        ]),
    }
}

#[cfg(platform_xiaohongshu)]
fn xiaohongshu_descriptor() -> PlatformDescriptor {
    PlatformDescriptor {
        kind: "xiaohongshu".to_string(),
        name: "小红书".to_string(),
        capabilities: PlatformCapabilities::new(vec![
            PlatformCapability::Chat,
            PlatformCapability::AutoReply,
            PlatformCapability::Account,
        ]),
    }
}

#[cfg(platform_douyin)]
fn douyin_descriptor() -> PlatformDescriptor {
    PlatformDescriptor {
        kind: "douyin".to_string(),
        name: "抖音".to_string(),
        capabilities: PlatformCapabilities::new(vec![
            PlatformCapability::Chat,
            PlatformCapability::AutoReply,
            PlatformCapability::Order,
            PlatformCapability::Account,
        ]),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn active_platform_descriptor_has_valid_capabilities() {
        let descriptors = builtin_descriptors();
        assert!(!descriptors.is_empty(), "至少应有一个编译期平台描述");
        for descriptor in &descriptors {
            for cap in &descriptor.capabilities.capabilities {
                assert!(cap
                    .as_str()
                    .chars()
                    .all(|c| c.is_ascii_lowercase() || c == '_'));
            }
        }
    }

    #[cfg(all(platform_xianyu, platform_xiaohongshu))]
    #[test]
    fn xianyu_has_coupon_but_xiaohongshu_not() {
        let descriptors = builtin_descriptors();
        let xianyu = descriptors
            .iter()
            .find(|d| d.kind == "xianyu")
            .expect("xianyu descriptor");
        let xhs = descriptors
            .iter()
            .find(|d| d.kind == "xiaohongshu")
            .expect("xhs descriptor");
        assert!(xianyu.capabilities.has(PlatformCapability::Coupon));
        assert!(!xhs.capabilities.has(PlatformCapability::Coupon));
    }

    #[test]
    fn capability_strings_are_snake_case() {
        let descriptors = builtin_descriptors();
        for descriptor in &descriptors {
            for cap in &descriptor.capabilities.capabilities {
                assert!(cap
                    .as_str()
                    .chars()
                    .all(|c| c.is_ascii_lowercase() || c == '_'));
            }
        }
    }
}
