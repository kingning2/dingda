//! MiMo CLI 插头：二进制、参数构建与模型发现。

use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::opencode_build_args;
use crate::runtime::model_discover::{parse_opencode_models, run_command};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

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

pub const MIMO: RuntimeDefinition = RuntimeDefinition {
    id: "mimo",
    name: "Mimo",
    description: "Mimo agent CLI",
    binary: "mimo",
    fallback_binaries: &[],
    path_env_var: "DINGDA_MIMO_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::JsonEventStream,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: true,
        prompt_via_stdin: true,
    },
    install_url: "https://mimo.xiaomi.com/mimocode",
    docs_url: "https://mimo.xiaomi.com/mimocode",
    external_mcp_injection: Some("mimo-env-content"),
    is_default: false,
    // CLI 与 OpenCode 同形：`run --format json` + `--dir` / `-s` / `-m`
    build_args: opencode_build_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
