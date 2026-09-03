//! 应用路径解析（backend、资源目录等）。

use std::path::PathBuf;

/// DingDa v2 Python backend 根目录（`backend/`）。
pub fn resolve_backend_dir() -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_BACKEND_DIR") {
        return PathBuf::from(path);
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir.join("../backend")
}
