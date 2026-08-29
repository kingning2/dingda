//! Camoufox 指纹浏览器插件。

use super::plugin_root;
use super::types::{BuiltinPlugin, PluginAsset, PluginFetch, PluginVerify};
use crate::contracts::PluginItem;
use std::path::{Path, PathBuf};

/// 插件稳定 id。
pub const ID: &str = "camoufox";

#[cfg(target_os = "windows")]
const ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-win.x86_64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
const ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-mac.arm64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "macos", not(target_arch = "aarch64")))]
const ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-mac.x86_64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "linux", target_arch = "aarch64"))]
const ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-lin.arm64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "linux", not(target_arch = "aarch64")))]
const ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-lin.x86_64.zip",
    extract_zip: true,
}];

#[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
const ASSETS: &[PluginAsset] = &[];

/// 注册表条目。
pub const SPEC: BuiltinPlugin = BuiltinPlugin {
    id: ID,
    name: "浏览器辅助",
    description: "用于闲鱼登录验证与滑块处理（约 500MB），按需下载，不随安装包分发。",
    fetch: PluginFetch::Http {
        assets: ASSETS,
        timeout_secs: 1800,
        verify: PluginVerify::CamoufoxExe,
    },
};

pub fn is_installed(plugins_dir: &Path) -> bool {
    find_executable(plugins_dir).is_some()
}

pub fn to_item(plugins_dir: &Path, error: Option<String>) -> PluginItem {
    let installed = is_installed(plugins_dir);
    let status = if error.is_some() {
        "failed"
    } else if installed {
        "installed"
    } else {
        "not_installed"
    };
    PluginItem {
        id: SPEC.id.to_string(),
        name: SPEC.name.to_string(),
        description: SPEC.description.to_string(),
        status: status.to_string(),
        error,
    }
}

/// 在插件目录中查找 Camoufox 可执行文件。
pub fn find_executable(plugins_dir: &Path) -> Option<PathBuf> {
    let root = plugin_root(plugins_dir, ID);
    if !root.is_dir() {
        return None;
    }
    let names: &[&str] = if cfg!(target_os = "windows") {
        &["camoufox.exe", "Camoufox.exe", "firefox.exe"]
    } else {
        &["camoufox", "camoufox-bin", "firefox"]
    };
    find_named_executable(&root, names)
}

fn find_named_executable(dir: &Path, names: &[&str]) -> Option<PathBuf> {
    for name in names {
        let direct = dir.join(name);
        if direct.is_file() {
            return Some(direct);
        }
    }
    let entries = std::fs::read_dir(dir).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if let Some(found) = find_named_executable(&path, names) {
                return Some(found);
            }
        } else if path.is_file() {
            let file_name = path.file_name()?.to_string_lossy();
            if names
                .iter()
                .any(|name| file_name.eq_ignore_ascii_case(name))
            {
                return Some(path);
            }
        }
    }
    None
}
