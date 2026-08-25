//! 闲鱼 cookies 辅助 — 从结构化 cookies 数组构造会话。
//!
//! 登录载体为 Chrome 扩展导出的快照：Playwright 登录后导出 cookies 数组，
//! Rust 侧将其转为 cookie 字符串并提取协议收发所需的字段。

use crate::contracts::contracts::ChannelCookie;

/// 从 cookies 数组构造 `name=value; ...` 字符串（供 HTTP/WS 请求头使用）。
///
/// 同名 Cookie 只保留一条：优先 `goofish.com`，其次 `taobao.com`，避免 Camoufox
/// 全量导出后 Header 里出现重复名导致 mtop `FAIL_SYS_ILLEGAL_ACCESS`。
pub fn cookies_to_string(cookies: &[ChannelCookie]) -> String {
    let mut best: std::collections::HashMap<&str, &ChannelCookie> =
        std::collections::HashMap::new();
    for cookie in cookies {
        if cookie.name.is_empty() || cookie.value.is_empty() {
            continue;
        }
        match best.get(cookie.name.as_str()) {
            None => {
                best.insert(&cookie.name, cookie);
            }
            Some(previous) => {
                if domain_preference(&cookie.domain) < domain_preference(&previous.domain) {
                    best.insert(&cookie.name, cookie);
                }
            }
        }
    }
    best.values()
        .map(|cookie| format!("{}={}", cookie.name, cookie.value))
        .collect::<Vec<_>>()
        .join("; ")
}

fn domain_preference(domain: &str) -> i32 {
    let lowered = domain.to_ascii_lowercase();
    if lowered.contains("goofish.com") {
        0
    } else if lowered.contains("taobao.com") {
        1
    } else if lowered.contains("alibaba.com") {
        2
    } else {
        50
    }
}

/// 从凭据（`ChannelAccount.credential` / 业务账号 `cookie`）解析 cookies 数组。
///
/// 兼容三种形态：
/// - **快照 JSON**（Chrome 扩展导出）：`{"cookies":[{...}], "env":{...}, ...}` → 取 `cookies`
/// - **cookies 数组 JSON**（登录后 / 滑块续期写回）：`[{name,value,...}, ...]`
/// - **旧 cookie 字符串**：`unb=...; _m_h5_tk=...` → 拆成无 domain 的 cookie
pub fn parse_credential(credential: &str) -> Vec<ChannelCookie> {
    // 尝试 JSON 解析。
    let parsed: serde_json::Value = serde_json::from_str(credential).unwrap_or_default();
    if parsed.is_object() {
        if let Some(cookies) = parsed.get("cookies").and_then(serde_json::Value::as_array) {
            return cookies
                .iter()
                .filter_map(|value| serde_json::from_value(value.clone()).ok())
                .collect();
        }
    }
    if parsed.is_array() {
        return parsed
            .as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|value| serde_json::from_value(value.clone()).ok())
                    .collect()
            })
            .unwrap_or_default();
    }
    // 旧 cookie 字符串。
    credential
        .split(';')
        .filter_map(|part| {
            let part = part.trim();
            if part.is_empty() {
                return None;
            }
            let (name, value) = part.split_once('=')?;
            Some(ChannelCookie {
                name: name.trim().to_string(),
                value: value.trim().to_string(),
                domain: String::new(),
                path: String::new(),
                expires: None,
                http_only: None,
                secure: None,
                same_site: None,
            })
        })
        .collect()
}

/// 把任意凭据形态规范成 HTTP `Cookie` 头：`name=value; ...`。
///
/// 滑块续期会把 Cookie 存成 JSON 数组；mtop / 商品同步仍吃 Header 字符串。
/// 统一经此函数，避免 `parse_cookies("[{...}]")` 读不到 `unb`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-21
///
/// # 参数
/// - `credential` — JSON 数组 / 快照 / `k=v;` 字符串
///
/// # 返回值
/// Header 用 Cookie 串；解析为空时回退原文（兼容极旧数据）。
pub fn credential_to_cookie_header(credential: &str) -> String {
    let header = cookies_to_string(&parse_credential(credential));
    if header.is_empty() {
        credential.trim().to_string()
    } else {
        header
    }
}

/// 取用户 id（`unb` cookie）。
pub fn my_id(cookies: &[ChannelCookie]) -> Option<String> {
    cookies
        .iter()
        .find(|cookie| cookie.name == "unb")
        .map(|cookie| cookie.value.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_cookies() -> Vec<ChannelCookie> {
        vec![
            ChannelCookie {
                name: "unb".into(),
                value: "U-123".into(),
                domain: crate::contracts::constants::xianyu::COOKIE_DOMAIN.into(),
                path: "/".into(),
                expires: None,
                http_only: Some(false),
                secure: Some(false),
                same_site: Some("Lax".into()),
            },
            ChannelCookie {
                name: "_m_h5_tk".into(),
                value: "token_rest".into(),
                domain: crate::contracts::constants::xianyu::COOKIE_DOMAIN.into(),
                path: "/".into(),
                expires: None,
                http_only: Some(true),
                secure: Some(false),
                same_site: None,
            },
            ChannelCookie {
                name: "".into(),
                value: "".into(),
                domain: "".into(),
                path: "".into(),
                expires: None,
                http_only: None,
                secure: None,
                same_site: None,
            },
        ]
    }

    #[test]
    fn cookies_to_string_joins_non_empty() {
        let str = cookies_to_string(&sample_cookies());
        assert!(str.contains("unb=U-123"));
        assert!(str.contains("_m_h5_tk=token_rest"));
        assert!(!str.contains("; ;")); // 空 cookie 被过滤
    }

    #[test]
    fn extracts_my_id() {
        let cookies = sample_cookies();
        assert_eq!(my_id(&cookies), Some("U-123".to_string()));
    }

    #[test]
    fn parse_credential_handles_all_forms() {
        // 旧 cookie 字符串。
        let legacy = parse_credential("unb=U-1; _m_h5_tk=tk_x; cookie2=c2");
        assert_eq!(my_id(&legacy), Some("U-1".to_string()));

        // cookies 数组 JSON。
        let array_json = r#"[{"name":"unb","value":"U-9","domain":".goofish.com","path":"/"}]"#;
        let from_array = parse_credential(array_json);
        assert_eq!(my_id(&from_array), Some("U-9".to_string()));

        // 快照 JSON（含 cookies 数组）。
        let snapshot_json = format!(
            r#"{{"capturedAt":"2026-08-11","env":{{}},"cookies":{},"headers":{{}}}}"#,
            array_json
        );
        let from_snapshot = parse_credential(&snapshot_json);
        assert_eq!(my_id(&from_snapshot), Some("U-9".to_string()));
    }

    #[test]
    fn credential_to_cookie_header_from_json_array() {
        let array_json = r#"[{"name":"unb","value":"2214350705775","domain":".goofish.com","path":"/"},{"name":"_m_h5_tk","value":"tk_x","domain":".goofish.com","path":"/"}]"#;
        let header = credential_to_cookie_header(array_json);
        assert!(header.contains("unb=2214350705775"));
        assert!(header.contains("_m_h5_tk=tk_x"));
        assert!(!header.trim_start().starts_with('['));
    }
}
