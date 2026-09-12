//! 托管下载 / 安装：把 CLI 拉到 `~/.dingda/v2/runtimes/<id>/`。
//!
//! 各 `defs/<id>.rs` 只填 `managed_download: Some(ManagedDownloadSpec { .. })`；
//! 下载 / 解压 / 落盘全部集中在本文件，禁止每个插头复制一份。
//! 路径解析在 [defs/base.rs](defs/base.rs)。

use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;

use common::logging::{self, Scope};
use crate::defs::base::fetch_text;
use crate::resolution::is_executable_file;
use crate::types::{ManagedDownloadSpec, RuntimeDefinition};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ManagedDownloadResult {
    pub agent_id: String,
    pub path: String,
    pub version: Option<String>,
    pub message: String,
}

impl RuntimeDefinition {
    /// 按 `managed_download` 规格下载并安装到托管目录。
    pub async fn download_managed(&self) -> Result<ManagedDownloadResult, String> {
        let spec = self
            .managed_download
            .ok_or_else(|| format!("暂不支持下载：{}", self.id))?;
        download_with_spec(self, spec).await
    }
}

async fn download_with_spec(
    definition: &RuntimeDefinition,
    spec: ManagedDownloadSpec,
) -> Result<ManagedDownloadResult, String> {
    let dest_dir = definition
        .managed_dir()
        .ok_or_else(|| "无法解析用户目录".to_string())?;
    let dest_bin = definition
        .managed_binary_path()
        .ok_or_else(|| "无法解析安装路径".to_string())?;
    let asset = (spec.asset_name)()?;
    let base = spec.release_base_url.trim_end_matches('/');

    fs::create_dir_all(&dest_dir).map_err(|e| format!("创建目录失败: {e}"))?;

    let url = match spec.version_file {
        Some(pointer) => {
            let version = fetch_version_pointer(&format!("{base}/{pointer}")).await?;
            format!("{base}/{version}/{asset}")
        }
        None => format!("{base}/{asset}"),
    };
    logging::log(
        Scope::Runtime,
        "开始下载",
        Some(&format!("{} {}", definition.id, url)),
    );

    let tmp_dir = dest_dir.join(".download-tmp");
    if tmp_dir.exists() {
        let _ = fs::remove_dir_all(&tmp_dir);
    }
    fs::create_dir_all(&tmp_dir).map_err(|e| format!("创建临时目录失败: {e}"))?;

    let local_name = Path::new(asset)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or(asset);
    let download_path = tmp_dir.join(local_name);
    download_file(&url, &download_path).await?;

    let wanted = definition.managed_binary_file_name();
    let source = if is_archive_name(local_name) {
        extract_archive(&download_path, &tmp_dir)?;
        find_extracted_binary(&tmp_dir, &wanted, local_name)
            .ok_or_else(|| format!("压缩包内未找到 {} 可执行文件", definition.binary))?
    } else {
        download_path
    };
    fs::copy(&source, &dest_bin).map_err(|e| format!("写入托管二进制失败: {e}"))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&dest_bin)
            .map_err(|e| format!("读取权限失败: {e}"))?
            .permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&dest_bin, perms).map_err(|e| format!("设置可执行权限失败: {e}"))?;
    }

    let _ = fs::remove_dir_all(&tmp_dir);

    let version = read_version(&dest_bin, definition.version_args).await;
    let path = dest_bin.display().to_string();
    logging::log(
        Scope::Runtime,
        "下载完成",
        Some(&format!(
            "id={} path={path} version={}",
            definition.id,
            version.as_deref().unwrap_or("?")
        )),
    );

    Ok(ManagedDownloadResult {
        agent_id: definition.id.to_string(),
        path,
        version,
        message: format!("{} 已安装到叮答托管目录", definition.name),
    })
}

/// 读取版本指针文件（如 Claude 的 `latest` → `2.1.263`）。
async fn fetch_version_pointer(url: &str) -> Result<String, String> {
    let text = fetch_text(url).await?;
    let version = text.trim();
    if version.is_empty() || !version.chars().all(|c| c.is_ascii_digit() || c == '.') {
        return Err(format!("版本指针无效: {version}"));
    }
    Ok(version.to_string())
}

fn is_archive_name(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    lower.ends_with(".zip") || lower.ends_with(".tar.gz") || lower.ends_with(".tgz")
}

async fn download_file(url: &str, dest: &Path) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .user_agent("dingda-v2")
        .redirect(reqwest::redirect::Policy::limited(10))
        .build()
        .map_err(|e| format!("创建 HTTP 客户端失败: {e}"))?;

    let response = client
        .get(url)
        .send()
        .await
        .map_err(|e| format!("下载失败: {e}"))?;
    if !response.status().is_success() {
        return Err(format!("下载失败：HTTP {}", response.status()));
    }
    let bytes = response
        .bytes()
        .await
        .map_err(|e| format!("读取下载内容失败: {e}"))?;
    fs::write(dest, &bytes).map_err(|e| format!("写入临时文件失败: {e}"))?;
    Ok(())
}

fn extract_archive(archive: &Path, dest: &Path) -> Result<(), String> {
    let name = archive
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();

    if name.ends_with(".zip") {
        extract_zip(archive, dest)
    } else if name.ends_with(".tar.gz") || name.ends_with(".tgz") {
        extract_tar_gz(archive, dest)
    } else {
        Err(format!("不支持的压缩格式: {name}"))
    }
}

fn extract_zip(archive: &Path, dest: &Path) -> Result<(), String> {
    #[cfg(windows)]
    {
        let status = std::process::Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                &format!(
                    "Expand-Archive -LiteralPath '{}' -DestinationPath '{}' -Force",
                    archive.display(),
                    dest.display()
                ),
            ])
            .status()
            .map_err(|e| format!("解压 zip 失败: {e}"))?;
        if !status.success() {
            return Err("解压 zip 失败".to_string());
        }
        Ok(())
    }
    #[cfg(not(windows))]
    {
        let status = std::process::Command::new("unzip")
            .args([
                "-o",
                &archive.to_string_lossy(),
                "-d",
                &dest.to_string_lossy(),
            ])
            .status()
            .map_err(|e| format!("解压 zip 失败（需要 unzip）: {e}"))?;
        if !status.success() {
            return Err("解压 zip 失败".to_string());
        }
        Ok(())
    }
}

fn extract_tar_gz(archive: &Path, dest: &Path) -> Result<(), String> {
    let status = std::process::Command::new("tar")
        .args([
            "-xzf",
            &archive.to_string_lossy(),
            "-C",
            &dest.to_string_lossy(),
        ])
        .status()
        .map_err(|e| format!("解压 tar.gz 失败: {e}"))?;
    if !status.success() {
        return Err("解压 tar.gz 失败".to_string());
    }
    Ok(())
}

fn find_extracted_binary(root: &Path, wanted: &str, asset_file: &str) -> Option<PathBuf> {
    let wanted_stem = wanted.trim_end_matches(".exe");
    let asset_stem = strip_archive_ext(asset_file);

    let direct = root.join(wanted);
    if is_executable_file(&direct) {
        return Some(direct);
    }
    if let Some(stem) = asset_stem.as_deref() {
        let by_asset = root.join(stem);
        if is_executable_file(&by_asset) {
            return Some(by_asset);
        }
    }

    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let entries = fs::read_dir(&dir).ok()?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            let name = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
            let matched = name == wanted
                || asset_stem.as_deref() == Some(name)
                || name.starts_with(&format!("{wanted_stem}-"));
            if matched && is_executable_file(&path) {
                return Some(path);
            }
        }
    }
    None
}

fn strip_archive_ext(name: &str) -> Option<String> {
    let lower = name.to_ascii_lowercase();
    let stem = if let Some(s) = lower.strip_suffix(".tar.gz") {
        &name[..s.len()]
    } else if let Some(s) = lower.strip_suffix(".tgz") {
        &name[..s.len()]
    } else if let Some(s) = lower.strip_suffix(".zip") {
        &name[..s.len()]
    } else if let Some(s) = lower.strip_suffix(".exe") {
        &name[..s.len()]
    } else {
        name
    };
    if stem.is_empty() {
        None
    } else {
        Some(stem.to_string())
    }
}

async fn read_version(binary: &Path, version_args: &[&str]) -> Option<String> {
    let mut cmd = tokio::process::Command::new(binary);
    cmd.args(version_args);
    let output = cmd.output().await.ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let line = text.lines().next()?.trim();
    if line.is_empty() {
        None
    } else {
        Some(line.to_string())
    }
}

#[cfg(test)]
mod tests {
    use crate::defs::{CLAUDE, CODEX, OPENCODE};

    #[test]
    fn managed_agents_support_download() {
        assert!(OPENCODE.supports_managed_download());
        assert!(CODEX.supports_managed_download());
        assert!(CLAUDE.supports_managed_download());
    }

    #[test]
    fn claude_uses_version_pointer() {
        let spec = CLAUDE.managed_download.expect("claude download");
        assert_eq!(spec.version_file, Some("latest"));
    }
}
