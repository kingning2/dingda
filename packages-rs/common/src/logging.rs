//! 壳的统一日志：北京时间 + 彩色 `[scope]` 前缀，打到 stderr。
//!
//! 所有壳内日志都走这里，不要再各模块自己拼 `eprintln!`。

use chrono::{FixedOffset, Utc};

/// 日志来源，决定前缀文字与颜色。
#[derive(Debug, Clone, Copy)]
pub enum Scope {
    /// 绿：CLI Agent 目录探测。
    Agent,
    /// 青：壳自身（Python 子进程、路径同步、Camoufox 解压）。
    Shell,
    /// 品红：前端转发过来的错误。
    Frontend,
    /// 黄：Runtime 插头（托管下载）。
    Runtime,
}

impl Scope {
    fn prefix(self) -> &'static str {
        match self {
            Scope::Agent => "\x1b[1;32m[agent]\x1b[0m",
            Scope::Shell => "\x1b[1;36m[shell]\x1b[0m",
            Scope::Frontend => "\x1b[1;35m[frontend]\x1b[0m",
            Scope::Runtime => "\x1b[1;33m[runtime]\x1b[0m",
        }
    }
}

/// 输出一条日志；`detail` 为 `None` 或空串时省略尾部。
pub fn log(scope: Scope, message: &str, detail: Option<&str>) {
    let prefix = scope.prefix();
    let timestamp = beijing_timestamp();
    match detail {
        Some(detail) if !detail.is_empty() => {
            eprintln!("{prefix} {timestamp} {message} {detail}");
        }
        _ => eprintln!("{prefix} {timestamp} {message}"),
    }
}

fn beijing_timestamp() -> String {
    let offset = FixedOffset::east_opt(8 * 3600).expect("beijing offset");
    Utc::now()
        .with_timezone(&offset)
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}
