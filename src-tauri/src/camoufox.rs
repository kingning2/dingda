//! Camoufox 平台 zip：按 OS/arch 选包，用 `zip` crate 解压到本地缓存。

use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use tauri::AppHandle;
use zip::ZipArchive;

use crate::paths::{data_dir, find_camoufox_exe, resolve_runtime_dir};

const STAMP_NAME: &str = ".extract-stamp";

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

/// zip 指纹：size + mtime，中断解压后可检测并重解。
fn zip_stamp(zip_path: &Path) -> Result<String, String> {
    let meta = fs::metadata(zip_path).map_err(|e| e.to_string())?;
    let mtime = meta
        .modified()
        .unwrap_or(SystemTime::UNIX_EPOCH)
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    Ok(format!("{}:{}", meta.len(), mtime))
}

/// 可启动条件：exe + properties.json（Python camoufox 校验配置用）+ stamp 对齐。
fn is_camoufox_ready(dest: &Path, zip_path: &Path) -> bool {
    if find_camoufox_exe(dest).is_none() {
        return false;
    }
    if !dest.join("properties.json").is_file() {
        return false;
    }
    let Ok(expected) = zip_stamp(zip_path) else {
        return false;
    };
    let stamp_path = dest.join(STAMP_NAME);
    let Ok(mut f) = File::open(&stamp_path) else {
        return false;
    };
    let mut got = String::new();
    if f.read_to_string(&mut got).is_err() {
        return false;
    }
    got.trim() == expected
}

/// 确保已解压并返回 camoufox 可执行文件路径。
pub fn ensure_camoufox_exe(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(path) = std::env::var("DINGDA_CAMOUFOX_EXE") {
        let p = PathBuf::from(path);
        if p.is_file() {
            return Ok(p);
        }
    }

    let Some(zip_path) = bundled_camoufox_zip(app) else {
        // 无包内 zip：若本地已有完整目录仍可用（dev 手工解压）
        let current = data_dir().join("camoufox").join("current");
        if let Some(exe) = find_camoufox_exe(&current) {
            if current.join("properties.json").is_file() {
                return Ok(exe);
            }
        }
        return Err(format!(
            "安装包缺少 Camoufox zip（期望 runtime/camoufox/camoufox-{}.zip）",
            camoufox_platform_tag()
        ));
    };

    let current = data_dir().join("camoufox").join("current");
    if is_camoufox_ready(&current, &zip_path) {
        return find_camoufox_exe(&current).ok_or_else(|| "camoufox ready but exe missing".into());
    }

    extract_camoufox_zip(&zip_path, &current)?;
    find_camoufox_exe(&current).ok_or_else(|| {
        format!(
            "解压后未找到 {}（zip={}）",
            exe_name(),
            zip_path.display()
        )
    })
}

/// 用官方 `zip` crate 解压到目标目录；逐文件写出，中断时不写 stamp。
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

    let stamp = zip_stamp(zip_path)?;
    let file = File::open(zip_path).map_err(|e| e.to_string())?;
    let mut archive = ZipArchive::new(file).map_err(|e| e.to_string())?;
    let total = archive.len();
    for i in 0..total {
        let mut entry = archive.by_index(i).map_err(|e| e.to_string())?;
        let name = entry
            .enclosed_name()
            .ok_or_else(|| format!("zip 非法路径: {}", entry.name()))?
            .to_path_buf();
        let out = dest.join(&name);
        if entry.is_dir() {
            fs::create_dir_all(&out).map_err(|e| e.to_string())?;
            continue;
        }
        if let Some(parent) = out.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let mut outfile = File::create(&out).map_err(|e| {
            format!("写入失败 {}: {e}", out.display())
        })?;
        std::io::copy(&mut entry, &mut outfile).map_err(|e| {
            format!("解压失败 {}: {e}", out.display())
        })?;
        if i == 0 || (i + 1) % 50 == 0 || i + 1 == total {
            eprintln!("[shell] camoufox extract {}/{}", i + 1, total);
        }
    }

    if find_camoufox_exe(dest).is_none() {
        return Err(format!(
            "zip 内未找到 {}（已解压到 {}）",
            exe_name(),
            dest.display()
        ));
    }
    if !dest.join("properties.json").is_file() {
        return Err(format!(
            "解压后缺少 properties.json（zip 可能损坏）：{}",
            zip_path.display()
        ));
    }

    let mut stamp_file = File::create(dest.join(STAMP_NAME)).map_err(|e| e.to_string())?;
    stamp_file
        .write_all(stamp.as_bytes())
        .map_err(|e| e.to_string())?;
    eprintln!("[shell] camoufox extract done entries={total}");
    Ok(())
}
