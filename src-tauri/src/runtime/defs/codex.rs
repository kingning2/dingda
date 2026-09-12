//! Codex CLI 插头：二进制、模型发现与托管下载规格。

use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use crate::runtime::model_discover::{parse_codex_debug_models, run_command, static_models};
use crate::runtime::types::{
    AuthParse, ManagedDownloadSpec, RuntimeAuth, RuntimeDefinition, RuntimeModel,
};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    if run_command(binary, &["login", "status"]).await.is_ok() {
        if let Ok(stdout) = run_command(binary, &["debug", "models"]).await {
            let parsed = parse_codex_debug_models(&stdout);
            if !parsed.is_empty() {
                return parsed;
            }
        }
    }
    static_models(&[
        ("gpt-5.5", "GPT-5.5"),
        ("gpt-5.4", "GPT-5.4"),
        ("gpt-5.4-mini", "GPT-5.4 mini"),
        ("gpt-5.3-codex", "GPT-5.3-Codex"),
        ("gpt-5.2", "GPT-5.2"),
        ("gpt-5.1", "GPT-5.1"),
        ("gpt-5", "GPT-5"),
        ("o3", "o3"),
        ("o4-mini", "o4-mini"),
    ])
}

/// Windows 为裸 `.exe`；macOS / Linux 为 `.tar.gz`（包内二进制带平台后缀）。
fn download_asset_name() -> Result<&'static str, String> {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("windows", "x86_64") => Ok("codex-x86_64-pc-windows-msvc.exe"),
        ("windows", "aarch64") => Ok("codex-aarch64-pc-windows-msvc.exe"),
        ("macos", "x86_64") => Ok("codex-x86_64-apple-darwin.tar.gz"),
        ("macos", "aarch64") => Ok("codex-aarch64-apple-darwin.tar.gz"),
        ("linux", "x86_64") => Ok("codex-x86_64-unknown-linux-musl.tar.gz"),
        ("linux", "aarch64") => Ok("codex-aarch64-unknown-linux-musl.tar.gz"),
        (os, arch) => Err(format!("当前平台暂不支持自动下载：{os}/{arch}")),
    }
}

pub const CODEX: RuntimeDefinition = RuntimeDefinition {
    id: "codex",
    name: "Codex",
    description: "OpenAI official CLI",
    binary: "codex",
    fallback_binaries: &[],
    path_env_var: "DINGDA_CODEX_PATH",
    version_args: &["--version"],
    auth: Some(RuntimeAuth {
        probe_args: &["login", "status"],
        parse: AuthParse::ExitCode,
        login_args: &["login"],
        login_message: "已在浏览器中打开 Codex 登录页，完成后请点击「扫描 Agent」刷新状态。",
    }),
    install_url: "https://github.com/openai/codex",
    docs_url: "https://developers.openai.com/codex",
    external_mcp_injection: Some("codex-mcp"),
    is_default: true,
    validate_executable: None,
    discover_models,
    managed_download: Some(ManagedDownloadSpec {
        release_base_url: "https://github.com/openai/codex/releases/latest/download",
        asset_name: download_asset_name,
        version_file: None,
    }),
};
