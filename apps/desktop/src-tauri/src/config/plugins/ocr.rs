//! OCR 文字识别语言包插件。

use super::types::{
    assets_present, remove_asset_files, BuiltinPlugin, PluginAsset, PluginFetch, PluginVerify,
};
use super::{plugin_install_dir, plugin_root};
use crate::contracts::PluginItem;
use std::path::Path;

/// 插件稳定 id。
pub const ID: &str = "ocr";

const ASSETS: &[PluginAsset] = &[
    PluginAsset {
        file_name: "eng.traineddata",
        url: "https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata",
        extract_zip: false,
    },
    PluginAsset {
        file_name: "chi_sim.traineddata",
        url: "https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata",
        extract_zip: false,
    },
];

/// 注册表条目。
pub const SPEC: BuiltinPlugin = BuiltinPlugin {
    id: ID,
    name: "文字识别",
    description: "图片文字识别语言包（简体中文 + 英文），按需下载，不随安装包分发。",
    fetch: PluginFetch::Http {
        assets: ASSETS,
        timeout_secs: 300,
        verify: PluginVerify::None,
    },
};

pub fn is_installed(plugins_dir: &Path, legacy_ocr_dir: &Path) -> bool {
    let new_dir = plugin_install_dir(plugins_dir, ID);
    assets_present(&new_dir, ASSETS) || assets_present(legacy_ocr_dir, ASSETS)
}

pub fn to_item(plugins_dir: &Path, legacy_ocr_dir: &Path, error: Option<String>) -> PluginItem {
    let installed = is_installed(plugins_dir, legacy_ocr_dir);
    status_item(&SPEC, installed, error)
}

/// 卸载时清理旧版 `{data}/tessdata` 语言包。
pub fn cleanup_legacy(legacy_ocr_dir: &Path, first_error: &mut Option<String>) {
    if !legacy_ocr_dir.exists() {
        return;
    }
    for asset in ASSETS {
        remove_asset_files(&legacy_ocr_dir.join(asset.file_name), first_error);
    }
    let _ = std::fs::remove_dir(legacy_ocr_dir);
}

pub fn install_subdir(plugins_dir: &Path) -> std::path::PathBuf {
    plugin_root(plugins_dir, ID).join("tessdata")
}

fn status_item(spec: &BuiltinPlugin, installed: bool, error: Option<String>) -> PluginItem {
    let status = if error.is_some() {
        "failed"
    } else if installed {
        "installed"
    } else {
        "not_installed"
    };
    PluginItem {
        id: spec.id.to_string(),
        name: spec.name.to_string(),
        description: spec.description.to_string(),
        status: status.to_string(),
        error,
    }
}
