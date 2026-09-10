//! Camoufox 平台 zip：按 OS/arch 选包，用 `zip` crate 解压到本地缓存。

use std::fs::{self, File};
use std::path::{Path, PathBuf};

use tauri::AppHandle;
use zip::ZipArchive;

use crate::paths::{data_dir, find_camoufox_exe, resolve_runtime_dir};

/// Camoufox Release 资源后缀（与官方 `camoufox-*-{tag}.zip` 一致）。
pub fn camoufox_platform_tag() -> &'static str {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("windows", "x86_64") => "win.x86_64",
        ("windows", "x86") => "win.i686",
        ("macos", "aarch64") => "mac.arm64",
        ("macos", "x86_64") => "mac.x86_64",
        ("linux", "aarch64") => "lin.arm64",
        ("linux", "x86_64") => "lin.x86_64",
        _ => "win.x86_64",
    }
}

fn exe_name() -> &'static str {
    if cfg!(windows) {
        "camoufox.exe"
    } else if cfg!(target_os = "macos") {
        "camoufox"
    } else {
        "camoufox-bin"
    }
}

/// 安装包内当前平台的 zip：`runtime/camoufox/camoufox-{tag}.zip`。
pub fn bundled_camoufox_zip(app: &AppHandle) -> Option<PathBuf> {
    let runtime = resolve_runtime_dir(app)?;
    let tag = camoufox_platform_tag();
    let named = runtime.join("camoufox").join(format!("camoufox-{tag}.zip"));
    if named.is_file() {
        return Some(named);
    }
    let dir = runtime.join("camoufox");
    if !dir.is_dir() {
        return None;
    }
    let mut matches = Vec::new();
    if let Ok(rd) = fs::read_dir(&dir) {
        for entry in rd.flatten() {
            let path = entry.path();
            let name = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
            if name.ends_with(".zip")
                && (name.ends_with(&format!("{tag}.zip")) || name.contains(&format!("-{tag}")))
            {
                matches.push(path);
            }
        }
    }
    matches.into_iter().next()
}

/// 确保已解压并返回 camoufox 可执行文件路径。
pub fn ensure_camoufox_exe(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(path) = std::env::var("DINGDA_CAMOUFOX_EXE") {
        let p = PathBuf::from(path);
        if p.is_file() {
            return Ok(p);
        }
    }

    let current = data_dir().join("camoufox").join("current");
    if let Some(exe) = find_camoufox_exe(&current) {
        return Ok(exe);
    }

    let Some(zip_path) = bundled_camoufox_zip(app) else {
        return Err(format!(
            "安装包缺少 Camoufox zip（期望 runtime/camoufox/camoufox-{}.zip）",
            camoufox_platform_tag()
        ));
    };

    extract_camoufox_zip(&zip_path, &current)?;
    find_camoufox_exe(&current).ok_or_else(|| {
        format!(
            "解压后未找到 {}（zip={}）",
            exe_name(),
            zip_path.display()
        )
    })
}

/// 用官方 `zip` crate 解压到目标目录。
pub fn extract_camoufox_zip(zip_path: &Path, dest: &Path) -> Result<(), String> {
    eprintln!(
        "[shell] camoufox extract zip={} -> {}",
        zip_path.display(),
        dest.display()
    );
    if dest.exists() {
        fs::remove_dir_all(dest).map_err(|e| e.to_string())?;
    }
    fs::create_dir_all(dest).map_err(|e| e.to_string())?;

    let file = File::open(zip_path).map_err(|e| e.to_string())?;
    let mut archive = ZipArchive::new(file).map_err(|e| e.to_string())?;
    archive.extract(dest).map_err(|e| e.to_string())?;

    if find_camoufox_exe(dest).is_none() {
        return Err(format!(
            "zip 内未找到 {}（已解压到 {}）",
            exe_name(),
            dest.display()
        ));
    }
    Ok(())
}
