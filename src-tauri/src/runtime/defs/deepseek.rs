use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::plain_exec_args;
use crate::runtime::model_discover::{
    discover_acp_models, parse_id_label_lines, parse_plain_id_lines, run_command,
    AcpDiscoveryConfig,
};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    for args in [
        &["models"][..],
        &["--list-models"][..],
        &["model", "list"][..],
    ] {
        if let Ok(stdout) = run_command(binary, args).await {
            let parsed = parse_id_label_lines(&stdout);
            if !parsed.is_empty() {
                return parsed;
            }
            let plain = parse_plain_id_lines(&stdout);
            if !plain.is_empty() {
                return plain;
            }
        }
    }
    let acp = discover_acp_models(binary, AcpDiscoveryConfig::default()).await;
    if !acp.is_empty() {
        return acp;
    }
    Vec::new()
}

pub const DEEPSEEK: RuntimeDefinition = RuntimeDefinition {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek terminal UI",
    binary: "codew",
    fallback_binaries: &["deepseek", "codewhale"],
    path_env_var: "DINGDA_DEEPSEEK_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::Plain,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        prompt_via_stdin: false,
    },
    install_url: "https://github.com/Hmbown/CodeWhale",
    docs_url: "https://github.com/Hmbown/CodeWhale/blob/main/README.md",
    external_mcp_injection: None,
    is_default: false,
    build_args: plain_exec_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
