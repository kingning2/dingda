//! Claude CLI 插头：二进制、模型发现与托管下载规格。

use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use crate::runtime::model_discover::static_models;
use crate::runtime::types::{
    ManagedDownloadSpec, RuntimeCapabilities, RuntimeDefinition, RuntimeModel,
};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    let _ = binary;
    Box::pin(async {
        static_models(&[
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ("claude-opus-4-6", "Claude Opus 4.6"),
            ("claude-sonnet-4-5", "Claude Sonnet 4.5"),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
            ("claude-opus-4-5", "Claude Opus 4.5"),
        ])
    })
}

/// 官方 CDN：`{base}/{version}/{platform}/claude[.exe]`；版本由 `version_file=latest` 解析。
fn download_asset_name() -> Result<&'static str, String> {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("windows", "x86_64") => Ok("win32-x64/claude.exe"),
        ("windows", "aarch64") => Ok("win32-arm64/claude.exe"),
        ("macos", "x86_64") => Ok("darwin-x64/claude"),
        ("macos", "aarch64") => Ok("darwin-arm64/claude"),
        ("linux", "x86_64") => Ok("linux-x64/claude"),
        ("linux", "aarch64") => Ok("linux-arm64/claude"),
        (os, arch) => Err(format!("当前平台暂不支持自动下载：{os}/{arch}")),
    }
}

pub const CLAUDE: RuntimeDefinition = RuntimeDefinition {
    id: "claude",
    name: "Claude",
    description: "Anthropic official CLI",
    binary: "claude",
    fallback_binaries: &[],
    path_env_var: "DINGDA_CLAUDE_PATH",
    version_args: &["--version"],
    capabilities: RuntimeCapabilities {
        login_capable: false,
    },
    install_url: "https://docs.anthropic.com/en/docs/claude-code/setup",
    docs_url: "https://docs.anthropic.com/en/docs/claude-code",
    external_mcp_injection: Some("claude-mcp-json"),
    is_default: false,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
    managed_download: Some(ManagedDownloadSpec {
        release_base_url: "https://downloads.claude.ai/claude-code-releases",
        asset_name: download_asset_name,
        version_file: Some("latest"),
    }),
};
