//! 内置插件包 — 每插件一文件，[`BUILTIN_PLUGINS`] 汇总注册。
//!
//! 新增插件：`plugins/{name}.rs` 导出 `ID` + `SPEC`，再在本文件 `mod` + 表中追加。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19
//! 更新：2026-08-26 — 拆分为目录。

mod camoufox;
mod embedding;
mod ocr;
mod types;

use crate::contracts::DingDaResult;
use crate::contracts::{PluginIpcListResponse, PluginItem};
use std::path::{Path, PathBuf};

pub use camoufox::find_executable as find_camoufox_executable;
pub use embedding::{
    cache_dir as embedding_cache_dir, is_installed as embedding_installed,
    to_item as embedding_item,
};
pub use types::{plugin_root, tmp_path, BuiltinPlugin, PluginAsset, PluginFetch, PluginVerify};

pub const PLUGIN_ID_OCR: &str = ocr::ID;
pub const PLUGIN_ID_CAMOUFOX: &str = camoufox::ID;
pub const PLUGIN_ID_EMBEDDING: &str = embedding::ID;

/// 内置可下载插件表。新增：加 `mod` + 往此数组追加 `xxx::SPEC`。
pub static BUILTIN_PLUGINS: &[BuiltinPlugin] = &[ocr::SPEC, camoufox::SPEC, embedding::SPEC];

/// 按 id 查找内置插件；未知 id 报错。
pub fn find_builtin(plugin_id: &str) -> DingDaResult<&'static BuiltinPlugin> {
    BUILTIN_PLUGINS
        .iter()
        .find(|plugin| plugin.id == plugin_id)
        .ok_or_else(|| {
            format!(
                "未知插件 id={plugin_id}；请从设置-插件列表选择已支持的插件（{}）",
                BUILTIN_PLUGINS
                    .iter()
                    .map(|plugin| plugin.id)
                    .collect::<Vec<_>>()
                    .join(" / ")
            )
            .into()
        })
}

/// 插件资源落盘目录（OCR 为 `plugins/ocr/tessdata`）。
pub fn plugin_install_dir(plugins_dir: &Path, plugin_id: &str) -> PathBuf {
    if plugin_id == ocr::ID {
        ocr::install_subdir(plugins_dir)
    } else {
        plugin_root(plugins_dir, plugin_id)
    }
}

impl BuiltinPlugin {
    /// 是否已在本地安装就绪。
    pub fn is_installed(&self, plugins_dir: &Path, legacy_ocr_dir: &Path) -> bool {
        match self.id {
            id if id == ocr::ID => ocr::is_installed(plugins_dir, legacy_ocr_dir),
            id if id == camoufox::ID => camoufox::is_installed(plugins_dir),
            id if id == embedding::ID => embedding::is_installed(plugins_dir),
            _ => false,
        }
    }

    /// 构造列表 / 失败回写用的 PluginItem。
    pub fn to_item(
        self,
        plugins_dir: &Path,
        legacy_ocr_dir: &Path,
        error: Option<String>,
    ) -> PluginItem {
        match self.id {
            id if id == ocr::ID => ocr::to_item(plugins_dir, legacy_ocr_dir, error),
            id if id == camoufox::ID => camoufox::to_item(plugins_dir, error),
            id if id == embedding::ID => embedding::to_item(plugins_dir, error),
            _ => PluginItem {
                id: self.id.to_string(),
                name: self.name.to_string(),
                description: self.description.to_string(),
                status: "not_installed".to_string(),
                error,
            },
        }
    }
}

/// 列出内置插件及其本地安装状态。
pub fn list_plugins(plugins_dir: &Path, legacy_ocr_dir: &Path) -> PluginIpcListResponse {
    PluginIpcListResponse {
        items: BUILTIN_PLUGINS
            .iter()
            .map(|plugin| plugin.to_item(plugins_dir, legacy_ocr_dir, None))
            .collect(),
    }
}

/// 返回指定插件的下载资源；未知 id 报错。
pub fn plugin_assets(plugin_id: &str) -> DingDaResult<&'static [PluginAsset]> {
    find_builtin(plugin_id)?.http_assets()
}

/// 卸载指定插件。
pub fn uninstall_plugin(
    plugins_dir: &Path,
    legacy_ocr_dir: &Path,
    plugin_id: &str,
) -> DingDaResult<PluginItem> {
    let plugin = find_builtin(plugin_id)?;
    let root = plugin_root(plugins_dir, plugin.id);
    let mut first_error: Option<String> = None;

    if root.exists() {
        if let Err(error) = std::fs::remove_dir_all(&root) {
            first_error = Some(format!(
                "删除插件目录失败 path={} reason={error}；请确认目录未被占用后重试",
                root.display()
            ));
        }
    }

    if plugin.id == ocr::ID {
        ocr::cleanup_legacy(legacy_ocr_dir, &mut first_error);
    }

    Ok(plugin.to_item(plugins_dir, legacy_ocr_dir, first_error))
}
