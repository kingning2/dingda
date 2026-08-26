//! 编译期渠道平台工具 — 与 Cargo feature / `DINGDA_CHANNEL_PLATFORMS` / `platform_*` cfg 对齐。
//!
//! 可同时启用多个站（如 `xianyu` + `ali1688`）。`ACTIVE_PLATFORM` 为主站
//!（优先闲鱼），供仍按单站展开的路径使用。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::domain::channel::ChannelKind;

/// 当前构建主站 id（编译期常量）。
pub const ACTIVE_PLATFORM: &str = env!("DINGDA_CHANNEL_PLATFORM");

/// 当前构建启用的全部站（逗号分隔，编译期常量）。
pub const ENABLED_PLATFORMS: &str = env!("DINGDA_CHANNEL_PLATFORMS");

/// 解析 [`ACTIVE_PLATFORM`] 为 [`ChannelKind`]。
///
/// # 返回值
/// 与主站对应的渠道类型；配置非法时在编译期失败。
pub const fn active_kind() -> ChannelKind {
    match ACTIVE_PLATFORM.as_bytes() {
        b"xianyu" => ChannelKind::Xianyu,
        b"ali1688" => ChannelKind::Ali1688,
        b"xiaohongshu" => ChannelKind::Xiaohongshu,
        b"douyin" => ChannelKind::Douyin,
        _ => panic!("未知 DINGDA_CHANNEL_PLATFORM"),
    }
}

/// 启用的平台 id 列表。
///
/// # 返回值
/// 编译期写入的站 id 切片（静态）。
pub fn enabled_platform_ids() -> impl Iterator<Item = &'static str> {
    ENABLED_PLATFORMS.split(',').filter(|item| !item.is_empty())
}

/// 判断给定渠道是否已编入本次构建。
///
/// # 参数
/// - `kind` — 待比较渠道类型
///
/// # 返回值
/// 已启用为 `true`。
pub fn is_active(kind: ChannelKind) -> bool {
    is_active_id(kind.as_str())
}

/// 判断字符串 id 是否已编入本次构建（`1688` 视为 `ali1688`）。
///
/// # 参数
/// - `platform_id` — 契约渠道标识
///
/// # 返回值
/// 已启用为 `true`。
pub fn is_active_id(platform_id: &str) -> bool {
    let canonical = match platform_id {
        "1688" => "ali1688",
        other => other,
    };
    enabled_platform_ids().any(|id| id == canonical)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn active_platform_is_enabled() {
        let kind = active_kind();
        assert_eq!(kind.as_str(), ACTIVE_PLATFORM);
        assert!(is_active(kind));
        assert!(is_active_id(ACTIVE_PLATFORM));
        assert!(!ENABLED_PLATFORMS.is_empty());
    }
}
