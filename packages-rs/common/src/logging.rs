//! 壳的统一日志：北京时间 + 彩色 `[scope]` 前缀，打到 stderr；
//! 壳启动后另落盘 `~/.dingda/v2/logs/shell.log`（纯文本，超 1MB 轮转保留 .old）。
//!
//! 所有壳内日志都走这里，不要再各模块自己拼 `eprintln!`。

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

use chrono::{FixedOffset, Utc};

const SHELL_LOG_MAX_BYTES: u64 = 1024 * 1024;

/// 日志来源，决定前缀文字与颜色。
#[derive(Debug, Clone, Copy)]
pub enum Scope {
    /// 青：壳自身（Python 子进程、路径同步、Camoufox 解压）。
    Shell,
    /// 品红：前端转发过来的错误。
    Frontend,
}

impl Scope {
    fn prefix(self) -> &'static str {
        match self {
            Scope::Shell => "\x1b[1;36m[shell]\x1b[0m",
            Scope::Frontend => "\x1b[1;35m[frontend]\x1b[0m",
        }
    }

    /// 文件里的纯文本前缀（无 ANSI）。
    fn tag(self) -> &'static str {
        match self {
            Scope::Shell => "shell",
            Scope::Frontend => "frontend",
        }
    }
}

static LOG_FILE: OnceLock<Option<Mutex<fs::File>>> = OnceLock::new();

/// 打开壳日志文件 `~/.dingda/v2/logs/shell.log`（追加；超 1MB 先改名 .old）。
/// 壳启动时调一次；打开失败只少个文件 sink，不影响主流程。
pub fn init_file_logging() {
    let path = crate::paths::data_dir().join("logs").join("shell.log");
    LOG_FILE.get_or_init(|| {
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        rotate_if_large(&path, SHELL_LOG_MAX_BYTES);
        match OpenOptions::new().create(true).append(true).open(&path) {
            Ok(file) => Some(Mutex::new(file)),
            Err(_) => None,
        }
    });
}

/// 超 `max_bytes` 就改名 `<原路径>.old`（覆盖旧备份）；失败静默，日志不挡主流程。
fn rotate_if_large(path: &Path, max_bytes: u64) {
    let Ok(meta) = fs::metadata(path) else {
        return;
    };
    if meta.len() <= max_bytes {
        return;
    }
    let mut old = path.as_os_str().to_os_string();
    old.push(".old");
    let _ = fs::rename(path, PathBuf::from(old));
}

/// 输出一条日志；`detail` 为 `None` 或空串时省略尾部。
pub fn log(scope: Scope, message: &str, detail: Option<&str>) {
    let prefix = scope.prefix();
    let timestamp = beijing_timestamp();
    match detail {
        Some(detail) if !detail.is_empty() => {
            eprintln!("{prefix} {timestamp} {message} {detail}");
            write_file(&format!("[{}] {timestamp} {message} {detail}", scope.tag()));
        }
        _ => {
            eprintln!("{prefix} {timestamp} {message}");
            write_file(&format!("[{}] {timestamp} {message}", scope.tag()));
        }
    }
}

fn write_file(line: &str) {
    let Some(lock) = LOG_FILE.get().and_then(|slot| slot.as_ref()) else {
        return;
    };
    if let Ok(mut file) = lock.lock() {
        let _ = writeln!(file, "{line}");
    }
}

fn beijing_timestamp() -> String {
    let offset = FixedOffset::east_opt(8 * 3600).expect("beijing offset");
    Utc::now()
        .with_timezone(&offset)
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_log_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("dingda-log-{}-{name}", std::process::id()))
    }

    #[test]
    fn small_file_stays_put() {
        let path = temp_log_path("small.log");
        fs::write(&path, "tiny").expect("write");
        rotate_if_large(&path, SHELL_LOG_MAX_BYTES);
        assert!(path.exists(), "小文件不该被轮转");
        let _ = fs::remove_file(&path);
    }

    #[test]
    fn large_file_moves_to_old() {
        let path = temp_log_path("large.log");
        fs::write(&path, "x".repeat((SHELL_LOG_MAX_BYTES + 1) as usize)).expect("write");
        rotate_if_large(&path, SHELL_LOG_MAX_BYTES);
        assert!(!path.exists(), "超限文件应改名让位");
        assert!(path.with_extension("log.old").exists(), "应有 .old 备份");
        let _ = fs::remove_file(path.with_extension("log.old"));
    }
}
