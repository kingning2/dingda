//! 内置插件共享类型与通用路径工具。

use crate::contracts::DingDaResult;
use std::path::{Path, PathBuf};

/// 插件需下载的单个资源。
#[derive(Debug, Clone, Copy)]
pub struct PluginAsset {
    /// 落盘文件名（如 `chi_sim.traineddata` / `camoufox.zip`）。
    pub file_name: &'static str,
    /// HTTP 下载地址。
    pub url: &'static str,
    /// 下载后是否解压（zip）。
    pub extract_zip: bool,
}

/// 下载完成后的校验 / 收尾。
#[derive(Debug, Clone, Copy)]
pub enum PluginVerify {
    /// 无额外校验。
    None,
    /// 必须能找到 Camoufox 可执行文件，并同步环境变量。
    CamoufoxExe,
}

/// 插件安装方式（决定 `plugin_download` 走哪条路径）。
#[derive(Debug, Clone, Copy)]
pub enum PluginFetch {
    /// HTTP 拉取 [`PluginAsset`] 列表。
    Http {
        assets: &'static [PluginAsset],
        timeout_secs: u64,
        verify: PluginVerify,
    },
    /// 经托管 `EmbeddingService::preload`（fastembed 自下载）。
    EmbeddingModel,
}

/// 内置插件元数据（注册表条目）。
#[derive(Debug, Clone, Copy)]
pub struct BuiltinPlugin {
    pub id: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    pub fetch: PluginFetch,
}

impl BuiltinPlugin {
    /// HTTP 资源列表；Embedding 无 HTTP 资产时返回空切片。
    pub fn http_assets(&self) -> DingDaResult<&'static [PluginAsset]> {
        match self.fetch {
            PluginFetch::Http { assets, .. } => {
                if assets.is_empty() {
                    return Err(format!("当前平台暂不支持 {} 插件下载", self.name).into());
                }
                Ok(assets)
            }
            PluginFetch::EmbeddingModel => Ok(&[]),
        }
    }

    pub fn http_timeout_secs(&self) -> u64 {
        match self.fetch {
            PluginFetch::Http { timeout_secs, .. } => timeout_secs,
            PluginFetch::EmbeddingModel => 600,
        }
    }
}

/// 插件根目录 `{plugins_dir}/{plugin_id}`。
pub fn plugin_root(plugins_dir: &Path, plugin_id: &str) -> PathBuf {
    plugins_dir.join(plugin_id)
}

/// 下载过程中的临时文件路径。
pub fn tmp_path(dest: &Path) -> PathBuf {
    dest.with_extension(format!(
        "{}.part",
        dest.extension()
            .and_then(|ext| ext.to_str())
            .unwrap_or("bin")
    ))
}

pub(crate) fn assets_present(dir: &Path, assets: &[PluginAsset]) -> bool {
    assets
        .iter()
        .filter(|asset| !asset.extract_zip)
        .all(|asset| dir.join(asset.file_name).is_file())
}

pub(crate) fn remove_asset_files(path: &Path, first_error: &mut Option<String>) {
    if let Err(error) = std::fs::remove_file(path) {
        if error.kind() != std::io::ErrorKind::NotFound && first_error.is_none() {
            *first_error = Some(format!(
                "删除插件文件失败 path={} reason={error}；请确认文件未被占用后重试",
                path.display()
            ));
        }
    }
    let tmp = tmp_path(path);
    let _ = std::fs::remove_file(tmp);
}
