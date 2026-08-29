//! 共享账号站点辅助 — 闲鱼 Cookie 分袋与平台规范化入口。
//!
//! 跨平台共享（两站共用）。1688 平台标识识别为内建数据（不再委托
//! `platform-ali1688` crate，避免共享层依赖具体 Provider）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

use crate::contracts::ChannelCookie;

/// 规范化平台标识；1688 变体返回 `Some("ali1688")`，小红书变体返回 `Some("xiaohongshu")`，其余 `None`。
pub fn normalize_platform(platform: &str) -> Option<&'static str> {
    match platform.trim().to_ascii_lowercase().as_str() {
        "ali1688" | "1688" | "alibaba1688" => Some("ali1688"),
        "xiaohongshu" | "xhs" => Some("xiaohongshu"),
        _ => None,
    }
}

/// 规范化平台标识（QR / IPC 路由用）。
///
/// 1688 变体（`ali1688` / `1688` / `alibaba1688`）识别为 `ali1688`，小红书识别为
/// `xiaohongshu`，其余默认闲鱼。
pub fn normalize_account_platform(platform: &str) -> &'static str {
    normalize_platform(platform).unwrap_or("xianyu")
}

/// 解析账号所属平台（对齐前端 `resolveAccountPlatform`）。
pub fn resolve_account_platform(account_id: &str, platform: &str) -> &'static str {
    if account_id.starts_with("1688:") {
        return "ali1688";
    }
    normalize_platform(platform).unwrap_or("xianyu")
}

/// 按闲鱼域过滤后拼成 `name=value; …` Cookie 头。
pub fn xianyu_cookie_header(cookies: &[ChannelCookie]) -> String {
    cookies
        .iter()
        .filter(|cookie| domain_matches_xianyu(&cookie.domain))
        .map(|cookie| format!("{}={}", cookie.name, cookie.value))
        .collect::<Vec<_>>()
        .join("; ")
}

/// 按小红书域过滤后拼成 `name=value; …` Cookie 头。
pub fn xiaohongshu_cookie_header(cookies: &[ChannelCookie]) -> String {
    cookies
        .iter()
        .filter(|cookie| domain_matches_xiaohongshu(&cookie.domain))
        .map(|cookie| format!("{}={}", cookie.name, cookie.value))
        .collect::<Vec<_>>()
        .join("; ")
}

/// Cookie 域名去重列表（不含值，供判定日志）。
pub fn cookie_domains_for_log(cookies: &[ChannelCookie]) -> Vec<String> {
    let mut domains: Vec<String> = cookies
        .iter()
        .map(|cookie| cookie.domain.clone())
        .filter(|domain| !domain.is_empty())
        .collect();
    domains.sort();
    domains.dedup();
    domains
}

fn domain_matches_xianyu(domain: &str) -> bool {
    let d = domain.to_lowercase();
    let shared = d.contains("taobao")
        || d.contains("tmall")
        || d.contains("alipay")
        || d.contains("alibaba.com");
    d.contains("goofish") || shared
}

fn domain_matches_xiaohongshu(domain: &str) -> bool {
    domain.to_lowercase().contains("xiaohongshu")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cookie(name: &str, value: &str, domain: &str) -> ChannelCookie {
        ChannelCookie {
            name: name.to_string(),
            value: value.to_string(),
            domain: domain.to_string(),
            path: "/".to_string(),
            expires: None,
            http_only: None,
            secure: None,
            same_site: None,
        }
    }

    #[test]
    fn normalize_defaults_to_xianyu() {
        assert_eq!(normalize_account_platform("xianyu"), "xianyu");
        assert_eq!(normalize_account_platform(""), "xianyu");
    }

    #[test]
    fn normalize_recognizes_1688_variants() {
        assert_eq!(normalize_account_platform("ali1688"), "ali1688");
        assert_eq!(normalize_account_platform("1688"), "ali1688");
        assert_eq!(normalize_account_platform("alibaba1688"), "ali1688");
        assert_eq!(normalize_account_platform("xianyu"), "xianyu");
    }

    #[test]
    fn normalize_platform_variants() {
        assert_eq!(normalize_platform("ali1688"), Some("ali1688"));
        assert_eq!(normalize_platform("1688"), Some("ali1688"));
        assert_eq!(normalize_platform("xianyu"), None);
    }

    #[test]
    fn normalize_recognizes_xiaohongshu() {
        assert_eq!(normalize_account_platform("xiaohongshu"), "xiaohongshu");
        assert_eq!(normalize_platform("xhs"), Some("xiaohongshu"));
        assert_eq!(
            resolve_account_platform("abc", "xiaohongshu"),
            "xiaohongshu"
        );
    }

    #[test]
    fn resolve_platform_prefers_1688_account_id_prefix() {
        assert_eq!(
            resolve_account_platform("1688:2200574208023", "xianyu"),
            "ali1688"
        );
        assert_eq!(resolve_account_platform("xy123", "ali1688"), "ali1688");
        assert_eq!(resolve_account_platform("xy123", ""), "xianyu");
    }

    #[test]
    fn builds_xianyu_cookie_header() {
        let cookies = vec![
            cookie("unb", "U1", ".taobao.com"),
            cookie("_m_h5_tk", "xy", ".goofish.com"),
            cookie("_m_h5_tk", "ali", ".1688.com"),
            cookie("x5sec", "1", ".1688.com"),
        ];
        let xy = xianyu_cookie_header(&cookies);
        assert!(xy.contains("unb=U1"));
        assert!(xy.contains("_m_h5_tk=xy"));
        assert!(!xy.contains("x5sec=1"));
        assert!(!xy.contains("_m_h5_tk=ali"));
    }

    #[test]
    fn builds_xiaohongshu_cookie_header() {
        let cookies = vec![
            cookie("web_session", "S1", ".xiaohongshu.com"),
            cookie("a1", "A1", ".xiaohongshu.com"),
            cookie("unb", "U1", ".goofish.com"),
        ];
        let xhs = xiaohongshu_cookie_header(&cookies);
        assert!(xhs.contains("web_session=S1"));
        assert!(xhs.contains("a1=A1"));
        assert!(!xhs.contains("unb=U1"));
    }
}
