//! 应用路径解析（server、bundled uv、国内镜像环境）。

use std::fs;
use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager};

use crate::camoufox;
use crate::logging::{self, Scope};

const DEFAULT_INDEX: &str = "https://mirrors.aliyun.com/pypi/simple/";
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

/// `resources/runtime`：安装包 resource，或开发态 `src-tauri/resources/runtime`。
pub fn resolve_runtime_dir(app: &AppHandle) -> Option<PathBuf> {
    if let Some(resource) = resolve_resource_dir(app) {
        let runtime = resource.join("runtime");
        if runtime.is_dir() {
            return Some(runtime);
        }
        let flat = resource.join("bin").join(uv_bin_name());
        if flat.is_file() {
            return Some(resource);
        }
    }
    // tauri dev：resource_dir 往往对不上，直接读源码树里的 resources
    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("resources")
        .join("runtime");
    if dev.is_dir() {
        return Some(dev);
    }
    None
}

/// 是否客户安装包（非 `tauri dev`）。只有此时才注入国内镜像 / 可写 venv。
pub fn is_packaged_install() -> bool {
    !cfg!(dev)
}

fn uv_bin_name() -> &'static str {
    if cfg!(windows) {
        "uv.exe"
    } else {
        "uv"
    }
}

/// 打包态优先用 resource 里的 uv；开发态用 PATH。
pub fn resolve_uv_bin(app: &AppHandle) -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_UV") {
        let p = PathBuf::from(path);
        if p.is_file() {
            return p;
        }
    }
    if is_packaged_install() {
        if let Some(runtime) = resolve_runtime_dir(app) {
            let bundled = runtime.join("bin").join(uv_bin_name());
            if bundled.is_file() {
                return bundled;
            }
        }
    }
    PathBuf::from(uv_bin_name())
}

/// 可写的 Server 工作副本：仅安装包从 resource 同步；开发态用仓库 `server/`。
pub fn ensure_server_workdir(app: &AppHandle) -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_SERVER_DIR") {
        if !path.trim().is_empty() {
            return PathBuf::from(path);
        }
    }

    if !is_packaged_install() {
        return resolve_server_dir();
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
        logging::log(
            Scope::Shell,
            &format!("server-runtime sync failed: {error}; fallback bundled read-only dir"),
            None,
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
            fs::read_to_string(&src_lock).unwrap_or_default().len()
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

/// 启动子进程环境：开发态不改 PyPI；安装包才注入国内镜像与可写 venv。
pub fn desktop_runtime_env(app: &AppHandle, server_dir: &Path) -> Vec<(String, String)> {
    let mut env = vec![
        ("DINGDA_SERVER_DIR".into(), server_dir.display().to_string()),
        ("PYTHONUTF8".into(), "1".into()),
    ];

    if is_packaged_install() {
        // 客户机免翻墙；阿里云 + pypi.org 兜底。tauri dev 不要注入。
        env.push(("UV_DEFAULT_INDEX".into(), DEFAULT_INDEX.into()));
        env.push((
            "UV_PYTHON_INSTALL_MIRROR".into(),
            PYTHON_INSTALL_MIRROR.into(),
        ));
        env.push(("UV_INDEX".into(), "https://pypi.org/simple".into()));

        let uv = resolve_uv_bin(app);
        env.push(("DINGDA_UV".into(), uv.display().to_string()));

        let venv = data_dir().join("venvs").join("server");
        env.push(("UV_PROJECT_ENVIRONMENT".into(), venv.display().to_string()));
    }

    match camoufox::ensure_camoufox_exe(app) {
        Ok(exe) => {
            logging::log(
                Scope::Shell,
                &format!("camoufox exe={}", exe.display()),
                None,
            );
            env.push(("DINGDA_CAMOUFOX_EXE".into(), exe.display().to_string()));
        }
        Err(error) if is_packaged_install() => {
            logging::log(
                Scope::Shell,
                &format!("camoufox missing in install package: {error}"),
                None,
            );
        }
        Err(_) => {
            // tauri dev 无 zip 时用本机 camoufox 缓存，不刷屏
        }
    }

    env
}
