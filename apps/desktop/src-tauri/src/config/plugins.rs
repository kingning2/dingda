//! 内置插件目录与本地安装状态。
//!
//! 每个插件落在 `{app_local_data}/plugins/{plugin_id}/` 下；OCR 语言包在
//! `plugins/ocr/tessdata/`；Camoufox 解压在 `plugins/camoufox/`。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19
//! 更新：2026-08-21 — 增加 Camoufox 指纹浏览器插件。

use crate::contracts::contracts::{PluginIpcListResponse, PluginItem};
use crate::contracts::DingDaResult;
use std::path::{Path, PathBuf};

/// OCR 插件稳定 id。
pub const PLUGIN_ID_OCR: &str = "ocr";

/// Camoufox 指纹浏览器插件稳定 id。
pub const PLUGIN_ID_CAMOUFOX: &str = "camoufox";

/// 插件需下载的单个资源。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
#[derive(Debug, Clone, Copy)]
pub struct PluginAsset {
    /// 落盘文件名（如 `chi_sim.traineddata` / `camoufox.zip`）。
    pub file_name: &'static str,
    /// HTTP 下载地址。
    pub url: &'static str,
    /// 下载后是否解压（zip）。
    pub extract_zip: bool,
}

/// OCR 简体中文 + 英文语言包（GitHub tessdata，不随安装包分发）。
const OCR_ASSETS: &[PluginAsset] = &[
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

#[cfg(target_os = "windows")]
const CAMOUFOX_ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-win.x86_64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
const CAMOUFOX_ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-mac.arm64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "macos", not(target_arch = "aarch64")))]
const CAMOUFOX_ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-mac.x86_64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "linux", target_arch = "aarch64"))]
const CAMOUFOX_ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-lin.arm64.zip",
    extract_zip: true,
}];

#[cfg(all(target_os = "linux", not(target_arch = "aarch64")))]
const CAMOUFOX_ASSETS: &[PluginAsset] = &[PluginAsset {
    file_name: "camoufox.zip",
    url: "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.28/camoufox-152.0.4-beta.28-lin.x86_64.zip",
    extract_zip: true,
}];

#[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
const CAMOUFOX_ASSETS: &[PluginAsset] = &[];

/// 插件根目录 `{plugins_dir}/{plugin_id}`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn plugin_root(plugins_dir: &Path, plugin_id: &str) -> PathBuf {
    plugins_dir.join(plugin_id)
}

/// 插件资源落盘目录（OCR 为 `plugins/ocr/tessdata`）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn plugin_install_dir(plugins_dir: &Path, plugin_id: &str) -> PathBuf {
    match plugin_id {
        PLUGIN_ID_OCR => plugin_root(plugins_dir, plugin_id).join("tessdata"),
        other => plugin_root(plugins_dir, other),
    }
}

/// 列出内置插件及其本地安装状态。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn list_plugins(plugins_dir: &Path, legacy_ocr_dir: &Path) -> PluginIpcListResponse {
    PluginIpcListResponse {
        items: vec![
            ocr_item(plugins_dir, legacy_ocr_dir, None),
            camoufox_item(plugins_dir, None),
        ],
    }
}

/// 返回指定插件的下载资源；未知 id 报错。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn plugin_assets(plugin_id: &str) -> DingDaResult<&'static [PluginAsset]> {
    match plugin_id {
        PLUGIN_ID_OCR => Ok(OCR_ASSETS),
        PLUGIN_ID_CAMOUFOX => {
            if CAMOUFOX_ASSETS.is_empty() {
                return Err("当前平台暂不支持 Camoufox 插件下载".into());
            }
            Ok(CAMOUFOX_ASSETS)
        }
        other => Err(format!(
            "未知插件 id={other}；请从设置-插件列表选择已支持的插件（ocr / camoufox）"
        )
        .into()),
    }
}

/// 卸载指定插件。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn uninstall_plugin(
    plugins_dir: &Path,
    legacy_ocr_dir: &Path,
    plugin_id: &str,
) -> DingDaResult<PluginItem> {
    match plugin_id {
        PLUGIN_ID_OCR => uninstall_ocr(plugins_dir, legacy_ocr_dir),
        PLUGIN_ID_CAMOUFOX => uninstall_camoufox(plugins_dir),
        other => Err(format!(
            "未知插件 id={other}；请从设置-插件列表选择已支持的插件（ocr / camoufox）"
        )
        .into()),
    }
}

/// 构造 OCR 插件条目。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn ocr_item(plugins_dir: &Path, legacy_ocr_dir: &Path, error: Option<String>) -> PluginItem {
    let installed = ocr_installed(plugins_dir, legacy_ocr_dir);
    let status = if error.is_some() {
        "failed"
    } else if installed {
        "installed"
    } else {
        "not_installed"
    };
    PluginItem {
        id: PLUGIN_ID_OCR.to_string(),
        name: "文字识别".to_string(),
        description: "图片文字识别语言包（简体中文 + 英文），按需下载，不随安装包分发。"
            .to_string(),
        status: status.to_string(),
        error,
    }
}

/// 构造 Camoufox 插件条目。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-21
///
/// # 参数
/// - `plugins_dir` — 插件根
/// - `error` — 可选失败信息
///
/// # 返回值
/// Camoufox 插件条目。
pub fn camoufox_item(plugins_dir: &Path, error: Option<String>) -> PluginItem {
    let installed = find_camoufox_executable(plugins_dir).is_some();
    let status = if error.is_some() {
        "failed"
    } else if installed {
        "installed"
    } else {
        "not_installed"
    };
    PluginItem {
        id: PLUGIN_ID_CAMOUFOX.to_string(),
        name: "浏览器辅助".to_string(),
        description: "用于闲鱼登录验证与滑块处理（约 500MB），按需下载，不随安装包分发。"
            .to_string(),
        status: status.to_string(),
        error,
    }
}

/// 在插件目录中查找 Camoufox 可执行文件。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-21
///
/// # 参数
/// - `plugins_dir` — 本应用插件根
///
/// # 返回值
/// 找到则返回绝对路径。
pub fn find_camoufox_executable(plugins_dir: &Path) -> Option<PathBuf> {
    let root = plugin_root(plugins_dir, PLUGIN_ID_CAMOUFOX);
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

/// 下载过程中的临时文件路径。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub fn tmp_path(dest: &Path) -> PathBuf {
    dest.with_extension(format!(
        "{}.part",
        dest.extension()
            .and_then(|ext| ext.to_str())
            .unwrap_or("bin")
    ))
}

fn ocr_installed(plugins_dir: &Path, legacy_ocr_dir: &Path) -> bool {
    let new_dir = plugin_install_dir(plugins_dir, PLUGIN_ID_OCR);
    assets_present(&new_dir, OCR_ASSETS) || assets_present(legacy_ocr_dir, OCR_ASSETS)
}

fn assets_present(dir: &Path, assets: &[PluginAsset]) -> bool {
    assets
        .iter()
        .filter(|asset| !asset.extract_zip)
        .all(|asset| dir.join(asset.file_name).is_file())
}

fn uninstall_ocr(plugins_dir: &Path, legacy_ocr_dir: &Path) -> DingDaResult<PluginItem> {
    let root = plugin_root(plugins_dir, PLUGIN_ID_OCR);
    let mut first_error: Option<String> = None;

    if root.exists() {
        if let Err(error) = std::fs::remove_dir_all(&root) {
            first_error = Some(format!(
                "删除插件目录失败 path={} reason={error}；请确认目录未被占用后重试",
                root.display()
            ));
        }
    }

    if legacy_ocr_dir.exists() {
        for asset in OCR_ASSETS {
            remove_asset_files(&legacy_ocr_dir.join(asset.file_name), &mut first_error);
        }
        let _ = std::fs::remove_dir(legacy_ocr_dir);
    }

    Ok(ocr_item(plugins_dir, legacy_ocr_dir, first_error))
}

fn uninstall_camoufox(plugins_dir: &Path) -> DingDaResult<PluginItem> {
    let root = plugin_root(plugins_dir, PLUGIN_ID_CAMOUFOX);
    let mut first_error: Option<String> = None;
    if root.exists() {
        if let Err(error) = std::fs::remove_dir_all(&root) {
            first_error = Some(format!(
                "删除 Camoufox 目录失败 path={} reason={error}；请确认未被占用后重试",
                root.display()
            ));
        }
    }
    Ok(camoufox_item(plugins_dir, first_error))
}

fn remove_asset_files(path: &Path, first_error: &mut Option<String>) {
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("dingda-plugin-test-{nanos}"));
        fs::create_dir_all(&dir).expect("mkdir");
        dir
    }

    #[test]
    fn list_includes_ocr_and_camoufox() {
        let root = temp_dir();
        let plugins_dir = root.join("plugins");
        let legacy = root.join("tessdata");
        let list = list_plugins(&plugins_dir, &legacy);
        assert_eq!(list.items.len(), 2);
        assert_eq!(list.items[0].id, PLUGIN_ID_OCR);
        assert_eq!(list.items[1].id, PLUGIN_ID_CAMOUFOX);
        assert_eq!(list.items[0].status, "not_installed");
        assert_eq!(list.items[1].status, "not_installed");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn list_installed_under_plugin_folder() {
        let root = temp_dir();
        let plugins_dir = root.join("plugins");
        let install_dir = plugin_install_dir(&plugins_dir, PLUGIN_ID_OCR);
        fs::create_dir_all(&install_dir).expect("mkdir");
        for asset in OCR_ASSETS {
            fs::write(install_dir.join(asset.file_name), b"stub").expect("write");
        }
        let list = list_plugins(&plugins_dir, &root.join("tessdata"));
        assert_eq!(list.items[0].status, "installed");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn camoufox_installed_when_exe_present() {
        let root = temp_dir();
        let plugins_dir = root.join("plugins");
        let bin_dir = plugin_root(&plugins_dir, PLUGIN_ID_CAMOUFOX).join("bin");
        fs::create_dir_all(&bin_dir).expect("mkdir");
        let exe_name = if cfg!(windows) {
            "camoufox.exe"
        } else {
            "camoufox"
        };
        fs::write(bin_dir.join(exe_name), b"stub").expect("write");
        assert!(find_camoufox_executable(&plugins_dir).is_some());
        let item = camoufox_item(&plugins_dir, None);
        assert_eq!(item.status, "installed");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn uninstall_removes_plugin_folder_only() {
        let root = temp_dir();
        let plugins_dir = root.join("plugins");
        let legacy = root.join("tessdata");
        let install_dir = plugin_install_dir(&plugins_dir, PLUGIN_ID_OCR);
        fs::create_dir_all(&install_dir).expect("mkdir");
        for asset in OCR_ASSETS {
            fs::write(install_dir.join(asset.file_name), b"stub").expect("write");
        }
        fs::write(root.join("other.txt"), b"keep").expect("write");

        uninstall_plugin(&plugins_dir, &legacy, PLUGIN_ID_OCR).expect("uninstall");

        assert!(!plugin_root(&plugins_dir, PLUGIN_ID_OCR).exists());
        assert!(root.join("other.txt").is_file());
        let after = list_plugins(&plugins_dir, &legacy);
        assert_eq!(after.items[0].status, "not_installed");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn assets_reject_unknown_plugin() {
        let error = plugin_assets("unknown").expect_err("unknown");
        assert!(error.to_string().contains("未知插件"));
    }
}
