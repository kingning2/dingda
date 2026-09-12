//! Runtime 插头抽象：托管目录与可执行文件路径解析。
//!
//! 各 `defs/<id>.rs` 只填 `RuntimeDefinition`（含可选 `managed_download`）。
//! 本文件只管「装在哪、怎么认出来」——下载 / 安装见 [../install.rs](../install.rs)。

use std::path::PathBuf;

use crate::resolution::{canonicalize_path, is_executable_file};
use crate::types::{ExecutableSource, ResolvedExecutable, RuntimeDefinition};

impl RuntimeDefinition {
    /// 是否支持叮答托管一键下载。
    pub fn supports_managed_download(&self) -> bool {
        self.managed_download.is_some()
    }

    /// `~/.dingda/v2/runtimes/<id>/`
    pub fn managed_dir(&self) -> Option<PathBuf> {
        home_dir().map(|home| {
            home.join(".dingda")
                .join("v2")
                .join("runtimes")
                .join(self.id)
        })
    }

    /// 托管二进制完整路径（Windows 带 `.exe`）。
    pub fn managed_binary_path(&self) -> Option<PathBuf> {
        Some(self.managed_dir()?.join(self.managed_binary_file_name()))
    }

    /// 托管目录已有可执行文件时返回（source = Managed）。
    pub fn resolve_managed(&self) -> Option<ResolvedExecutable> {
        if !self.supports_managed_download() {
            return None;
        }
        let path = self.managed_binary_path()?;
        if !is_executable_file(&path) {
            return None;
        }
        Some(ResolvedExecutable {
            path: canonicalize_path(&path),
            source: ExecutableSource::Managed,
        })
    }

    /// 托管二进制的文件名（Windows 带 `.exe`）；安装与探测共用。
    pub(crate) fn managed_binary_file_name(&self) -> String {
        #[cfg(windows)]
        {
            format!("{}.exe", self.binary)
        }
        #[cfg(not(windows))]
        {
            self.binary.to_string()
        }
    }
}

/// 用户主目录（`HOME` → `USERPROFILE`）。托管路径解析要用。
pub(crate) fn home_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(PathBuf::from)
        .or_else(|| std::env::var("USERPROFILE").ok().map(PathBuf::from))
}

/// GET 一个文本资源（版本指针、models.dev 目录）。非 2xx 或网络失败都返回 `Err`。
pub(crate) async fn fetch_text(url: &str) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .user_agent("dingda-v2")
        .redirect(reqwest::redirect::Policy::limited(10))
        .build()
        .map_err(|e| format!("创建 HTTP 客户端失败: {e}"))?;
    let response = client
        .get(url)
        .send()
        .await
        .map_err(|e| format!("请求失败 {url}: {e}"))?;
    if !response.status().is_success() {
        return Err(format!("请求失败 {url}：HTTP {}", response.status()));
    }
    response
        .text()
        .await
        .map_err(|e| format!("读取响应失败 {url}: {e}"))
}

#[cfg(test)]
mod tests {
    use crate::defs::OPENCODE;

    #[test]
    fn managed_path_shape() {
        let path = OPENCODE.managed_binary_path().expect("home");
        let text = path.to_string_lossy();
        assert!(text.contains(".dingda"));
        assert!(text.contains("runtimes"));
        assert!(text.contains("opencode"));
    }
}
