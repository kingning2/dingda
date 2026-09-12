//! 应用路径解析（server、bundled uv、可写工作副本）。
//!
//! 职责：
//!     把「壳需要的目录在哪」集中成一组纯路径函数；不启动进程、不碰 Camoufox。
//!
//! 设计说明：
//!     - 有两个基准目录，均由壳在启动时注入：
//!       `set_app_root()` = 壳包目录（`packages-rs/client`），`resources/runtime` 用它；
//!       `set_repo_root()` = 仓库根，Python uv workspace 根（`pyproject.toml` / `uv.lock`）用它
//!     - 不能自己算：本文件在 `packages-rs/common`，`env!("CARGO_MANIFEST_DIR")`
//!       只会指向本包目录
//!     - 国内镜像 / venv / Camoufox exe 属「Python 启动环境」，见 `python`
//!     - `find_camoufox_exe` 属 Camoufox 知识，见 `camoufox`

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use tauri::{AppHandle, Manager};

use crate::logging::{self, Scope};

static APP_ROOT: OnceLock<PathBuf> = OnceLock::new();
static REPO_ROOT: OnceLock<PathBuf> = OnceLock::new();

/// 由壳在 `run()` 最开始注入「壳包目录」（`packages-rs/client`）。
///
/// 开发态 `resources/runtime` 以它为基准。
/// 之所以不直接用 `env!("CARGO_MANIFEST_DIR")`：本文件在 `packages-rs/common`，
/// 该宏只会指向本包目录，而不是壳目录。
pub fn set_app_root(root: PathBuf) {
    let _ = APP_ROOT.set(root);
}

/// 由壳在 `run()` 最开始注入「仓库根」。
///
/// 开发态 Python uv workspace 根以它为基准（`<repo>/pyproject.toml`）。
pub fn set_repo_root(root: PathBuf) {
    let _ = REPO_ROOT.set(root);
}

/// 壳包目录；未注入时回退到本包编译期目录（仅测试场景）。
fn app_root() -> PathBuf {
    APP_ROOT
        .get()
        .cloned()
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")))
}

/// 仓库根；未注入时按 `packages-rs/<pkg>` 的布局回退两级（仅测试场景）。
fn repo_root() -> PathBuf {
    REPO_ROOT
        .get()
        .cloned()
        .unwrap_or_else(|| app_root().join("..").join(".."))
}

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

/// 开发态：仓库根（Python uv workspace 根）；可用 `DINGDA_SERVER_DIR` 覆盖。
///
/// 目录里要有根 `pyproject.toml`（`[tool.uv.workspace]`）、`uv.lock` 与
/// `packages-py/`；壳在该目录跑 `uv sync --frozen` 后 `uv run python -m api`。
pub fn resolve_server_dir() -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_SERVER_DIR") {
        if !path.trim().is_empty() {
            return PathBuf::from(path);
        }
    }
    repo_root()
}

/// 安装包 resource 根（Tauri 解压出的 resources）。
pub fn resolve_resource_dir(app: &AppHandle) -> Option<PathBuf> {
    app.path().resource_dir().ok()
}

/// `resources/runtime`：安装包 resource，或开发态「壳包目录」下的 `resources/runtime`。
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
    let dev = app_root().join("resources").join("runtime");
    if dev.is_dir() {
        return Some(dev);
    }
    None
}

static DEV_MODE: OnceLock<bool> = OnceLock::new();

/// 由壳在 `run()` 最开始注入「当前是否 `tauri dev`」。
///
/// `cfg(dev)` 由 `tauri_build::build()` 在**壳的 build.rs** 里下发；本包没有
/// build.rs，拿不到该 cfg，若直接写 `cfg!(dev)` 会恒为 false，把 dev 误判成
/// 安装包（进而注入国内镜像、走打包态 uv）。故必须由壳显式注入。
pub fn set_dev_mode(is_dev: bool) {
    let _ = DEV_MODE.set(is_dev);
}

/// 是否客户安装包（非 `tauri dev`）。只有此时才注入国内镜像 / 可写 venv。
///
/// 未注入时按「安装包」处理，与 release 语义一致。
pub fn is_packaged_install() -> bool {
    !DEV_MODE.get().copied().unwrap_or(false)
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

/// 可写的 Server 工作副本：仅安装包从 resource 同步；开发态用仓库根。
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
            if old.trim() == stamp && dst.join("packages-py").is_dir() {
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
