//! Python 子进程的启动环境变量。
//!
//! 职责：
//!     算出拉起 uvicorn 需要注入的环境：Server 目录、国内镜像、uv、可写 venv、
//!     Camoufox 可执行文件路径。只返回数据，不启动进程。
//!
//! 设计说明：
//!     - 开发态（`tauri dev`）不注入国内镜像与 venv，避免污染本机环境
//!     - 原实现放在 `common::paths`，因它是 Python 关注点而迁入本包，
//!       同时也打断了 paths ↔ camoufox 的循环依赖

use std::path::Path;

use camoufox::ensure_camoufox_exe;
use common::logging::{self, Scope};
use common::paths::{data_dir, is_packaged_install, resolve_uv_bin};
use tauri::AppHandle;

const DEFAULT_INDEX: &str = "https://mirrors.aliyun.com/pypi/simple/";
const PYTHON_INSTALL_MIRROR: &str =
    "https://registry.npmmirror.com/-/binary/python-build-standalone";

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

    match ensure_camoufox_exe(app) {
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
