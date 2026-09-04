//! 外部 Agent 系统前言：用 Markdown 编写，启动时统一拼进 prompt。

const SYSTEM_MD: &str = include_str!("dingda-system.md");

/// 编译期嵌入的叮答系统前言（trim 后）。
pub fn dingda_system_prompt() -> &'static str {
    SYSTEM_MD.trim()
}

/// 系统前言 + 用户原文；空用户消息只返回前言。
pub fn compose_agent_prompt(user_prompt: &str) -> String {
    let system = dingda_system_prompt();
    let user = user_prompt.trim();
    if user.is_empty() {
        return system.to_string();
    }
    format!("{system}\n\n---\n\n{user}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn system_mentions_xianyu_and_pending_1688() {
        let text = dingda_system_prompt();
        assert!(text.contains("闲鱼") || text.contains("xianyu"));
        assert!(text.contains("1688"));
        assert!(text.contains("未接入") || text.contains("待核"));
    }

    #[test]
    fn compose_puts_user_after_separator() {
        let out = compose_agent_prompt("帮我找最近好卖的");
        assert!(out.contains("选品") || out.contains("闲鱼"));
        assert!(out.contains("---"));
        assert!(out.ends_with("帮我找最近好卖的"));
    }
}
