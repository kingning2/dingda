//! 应用路径解析（server、bundled uv、国内镜像环境）。

use std::fs;
use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager};

use crate::camoufox;

const DEFAULT_INDEX: &str = "https://pypi.tuna.tsinghua.edu.cn/simple";
const PYTHON_INSTALL_MIRROR: &str =
    "https://registry.npmmirror.com/-/binary/python-build-standalone";

/// 桌面数据根：`~/.dingda/v2`（与 Python `data_dir()` 对齐）。
pub fn data_dir() -> PathBuf {
    dirs_home()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".dingda")
        .join("v2")
}

fn dirs_home() -> Option<PathBuf> {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
}

/// 开发态：仓库 `server/`；可用 `DINGDA_SERVER_DIR` 覆盖。
pub fn resolve_server_dir() -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_SERVER_DIR") {
        if !path.trim().is_empty() {
            return PathBuf::from(path);
        }
    }
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir.join("../server")
}

/// 安装包 resource 根（Tauri 解压出的 resources）。
pub fn resolve_resource_dir(app: &AppHandle) -> Option<PathBuf> {
    app.path().resource_dir().ok()
}

/// `resources/runtime`（prepare-desktop-runtime 产出）。
pub fn resolve_runtime_dir(app: &AppHandle) -> Option<PathBuf> {
    let resource = resolve_resource_dir(app)?;
    let runtime = resource.join("runtime");
    if runtime.is_dir() {
        Some(runtime)
    } else {
        let flat = resource.join("bin").join(uv_bin_name());
        if flat.is_file() {
            Some(resource)
        } else {
            None
        }
    }
}

fn uv_bin_name() -> &'static str {
    if cfg!(windows) {
        "uv.exe"
    } else {
        "uv"
    }
}

/// 打包态优先用 resource 里的 uv；否则 PATH 上的 uv。
pub fn resolve_uv_bin(app: &AppHandle) -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_UV") {
        let p = PathBuf::from(path);
        if p.is_file() {
            return p;
        }
    }
    if let Some(runtime) = resolve_runtime_dir(app) {
        let bundled = runtime.join("bin").join(uv_bin_name());
        if bundled.is_file() {
            return bundled;
        }
    }
    PathBuf::from(uv_bin_name())
}

/// 可写的 Server 工作副本：从 resource 同步后供 `uv sync`。
pub fn ensure_server_workdir(app: &AppHandle) -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_SERVER_DIR") {
        if !path.trim().is_empty() {
            return PathBuf::from(path);
        }
    }

    let Some(runtime) = resolve_runtime_dir(app) else {
        return resolve_server_dir();
    };
    let bundled_server = runtime.join("server");
    if !bundled_server.is_dir() {
        return resolve_server_dir();
    }

    let work = data_dir().join("server-runtime");
    if let Err(error) = sync_dir_if_needed(&bundled_server, &work) {
        eprintln!(
            "[shell] server-runtime sync failed: {error}; fallback bundled read-only dir"
        );
        return bundled_server;
    }
    work
}

fn sync_dir_if_needed(src: &Path, dst: &Path) -> Result<(), String> {
    let marker = dst.join(".runtime-stamp");
    let src_lock = src.join("uv.lock");
    let stamp = if src_lock.is_file() {
        format!(
            "{}:{}",
            src_lock.metadata().map(|m| m.len()).unwrap_or(0),
            fs::read_to_string(&src_lock)
                .unwrap_or_default()
                .len()
        )
    } else {
        "no-lock".into()
    };

    if marker.is_file() {
        if let Ok(old) = fs::read_to_string(&marker) {
            if old.trim() == stamp && dst.join("src").is_dir() {
                return Ok(());
            }
        }
    }

    if dst.exists() {
        let _ = fs::remove_dir_all(dst);
    }
    copy_dir_recursive(src, dst)?;
    fs::write(&marker, stamp).map_err(|e| e.to_string())?;
    Ok(())
}

fn copy_dir_recursive(src: &Path, dst: &Path) -> Result<(), String> {
    fs::create_dir_all(dst).map_err(|e| e.to_string())?;
    for entry in fs::read_dir(src).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let ty = entry.file_type().map_err(|e| e.to_string())?;
        let to = dst.join(entry.file_name());
        if ty.is_dir() {
            copy_dir_recursive(&entry.path(), &to)?;
        } else if ty.is_file() {
            fs::copy(entry.path(), &to).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// 在目录树里找 camoufox 启动器（供 camoufox 模块复用）。
pub fn find_camoufox_exe(root: &Path) -> Option<PathBuf> {
    let names: &[&str] = if cfg!(windows) {
        &["camoufox.exe"]
    } else if cfg!(target_os = "macos") {
        &["camoufox", "camoufox-bin"]
    } else {
        &["camoufox-bin", "camoufox"]
    };
    for name in names {
        let direct = root.join(name);
        if direct.is_file() {
            return Some(direct);
        }
    }
    // macOS .app
    let mac = root
        .join("Camoufox.app")
        .join("Contents")
        .join("MacOS")
        .join("camoufox");
    if mac.is_file() {
        return Some(mac);
    }
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let rd = match fs::read_dir(&dir) {
            Ok(rd) => rd,
            Err(_) => continue,
        };
        for entry in rd.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            let fname = path.file_name().and_then(|s| s.to_str()).unwrap_or("");
            if names.contains(&fname) {
                return Some(path);
            }
        }
    }
    None
}

/// 启动子进程时注入的国内镜像与路径环境。
pub fn desktop_runtime_env(app: &AppHandle, server_dir: &Path) -> Vec<(String, String)> {
    let mut env = vec![
        ("DINGDA_SERVER_DIR".into(), server_dir.display().to_string()),
        ("UV_DEFAULT_INDEX".into(), DEFAULT_INDEX.into()),
        (
            "UV_PYTHON_INSTALL_MIRROR".into(),
            PYTHON_INSTALL_MIRROR.into(),
        ),
        ("PYTHONUTF8".into(), "1".into()),
    ];

    let uv = resolve_uv_bin(app);
    env.push(("DINGDA_UV".into(), uv.display().to_string()));

    let venv = data_dir().join("venvs").join("server");
    env.push((
        "UV_PROJECT_ENVIRONMENT".into(),
        venv.display().to_string(),
    ));

    match camoufox::ensure_camoufox_exe(app) {
        Ok(exe) => {
            eprintln!("[shell] camoufox exe={}", exe.display());
            env.push(("DINGDA_CAMOUFOX_EXE".into(), exe.display().to_string()));
        }
        Err(error) => {
            eprintln!("[shell] camoufox not ready: {error}");
        }
    }

    env
}
