//! Claude CLI 插头：二进制、模型发现与托管下载规格。

use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use crate::runtime::model_discover::{fetch_models_dev_anthropic, static_models};
use crate::runtime::types::{
    AuthParse, ManagedDownloadSpec, RuntimeAuth, RuntimeDefinition, RuntimeModel,
};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    let _ = binary;
    Box::pin(discover())
}

/// `claude` 没有列模型的子命令，账号侧可用模型也拿不到，所以目录走 models.dev 的
/// anthropic provider；拉不到（离线 / 接口变了）就回落静态列表。
async fn discover() -> Vec<RuntimeModel> {
    let remote = fetch_models_dev_anthropic().await;
    if !remote.is_empty() {
        return remote;
    }
    static_models(&[
        ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ("claude-opus-4-6", "Claude Opus 4.6"),
        ("claude-sonnet-4-5", "Claude Sonnet 4.5"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
        ("claude-opus-4-5", "Claude Opus 4.5"),
    ])
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
    auth: Some(RuntimeAuth {
        probe_args: &["auth", "status"],
        parse: AuthParse::JsonLoggedIn,
        login_args: &["auth", "login"],
        login_message: "已调用 claude auth login，请在浏览器完成授权后点「扫描 Agent」。",
    }),
    install_url: "https://docs.anthropic.com/en/docs/claude-code/setup",
    docs_url: "https://docs.anthropic.com/en/docs/claude-code",
    external_mcp_injection: Some("claude-mcp-json"),
    is_default: false,
    validate_executable: None,
    discover_models,
    managed_download: Some(ManagedDownloadSpec {
        release_base_url: "https://downloads.claude.ai/claude-code-releases",
        asset_name: download_asset_name,
        version_file: Some("latest"),
    }),
};
