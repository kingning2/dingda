//! 应用路径解析（server、资源目录等）。

use std::path::PathBuf;

/// DingDa v2 Python Server 根目录（`server/`）。
pub fn resolve_server_dir() -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_SERVER_DIR") {
        return PathBuf::from(path);
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir.join("../server")
}
