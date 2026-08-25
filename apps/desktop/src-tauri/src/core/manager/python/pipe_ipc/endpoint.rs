//! IPC 端点路径（Windows 命名管道名 / Unix socket 文件路径）。

use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct IpcEndpoint {
    path: PathBuf,
}

impl IpcEndpoint {
    #[must_use]
    pub fn from_path(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    /// 由进程 id 派生默认端点（spawn 前由 Rust 决定，经 `--ipc` 传给 Python）。
    #[must_use]
    pub fn for_pid(pid: u32) -> Self {
        #[cfg(windows)]
        {
            Self {
                path: PathBuf::from(format!(r"\\.\pipe\dingda-sidecar-{pid}")),
            }
        }
        #[cfg(unix)]
        {
            Self {
                path: std::env::temp_dir().join(format!("dingda-sidecar-{pid}.sock")),
            }
        }
        #[cfg(not(any(windows, unix)))]
        {
            let _ = pid;
            Self {
                path: PathBuf::from("dingda-sidecar.ipc"),
            }
        }
    }

    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    #[must_use]
    pub fn display(&self) -> String {
        self.path.display().to_string()
    }
}
