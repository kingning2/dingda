//! OpenCode 插头：静态定义 + 模型发现；下载走 `defs/base` 统一实现。

use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use crate::runtime::model_discover::{parse_opencode_models, run_command};
use crate::runtime::types::{
    ManagedDownloadSpec, RuntimeCapabilities, RuntimeDefinition, RuntimeModel,
};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    if let Ok(stdout) = run_command(binary, &["models", "--verbose"]).await {
        let parsed = parse_opencode_models(&stdout);
        if !parsed.is_empty() {
            return parsed;
        }
    }
    if let Ok(stdout) = run_command(binary, &["models"]).await {
        return parse_opencode_models(&stdout);
    }
    Vec::new()
}

fn download_asset_name() -> Result<&'static str, String> {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("windows", "x86_64") => Ok("opencode-windows-x64.zip"),
        ("windows", "aarch64") => Ok("opencode-windows-arm64.zip"),
        ("macos", "x86_64") => Ok("opencode-darwin-x64.zip"),
        ("macos", "aarch64") => Ok("opencode-darwin-arm64.zip"),
        ("linux", "x86_64") => Ok("opencode-linux-x64.tar.gz"),
        ("linux", "aarch64") => Ok("opencode-linux-arm64.tar.gz"),
        (os, arch) => Err(format!("当前平台暂不支持自动下载：{os}/{arch}")),
    }
}

pub const OPENCODE: RuntimeDefinition = RuntimeDefinition {
    id: "opencode",
    name: "OpenCode",
    description: "Open-source agent CLI",
    binary: "opencode",
    fallback_binaries: &["opencode-cli"],
    path_env_var: "DINGDA_OPENCODE_PATH",
    version_args: &["--version"],
    capabilities: RuntimeCapabilities {
        login_capable: false,
    },
    install_url: "https://opencode.ai/docs",
    docs_url: "https://github.com/sst/opencode",
    external_mcp_injection: Some("opencode-env-content"),
    is_default: false,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
    managed_download: Some(ManagedDownloadSpec {
        release_base_url: "https://github.com/anomalyco/opencode/releases/latest/download",
        asset_name: download_asset_name,
        version_file: None,
    }),
};
