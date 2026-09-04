use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::empty_args;
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    let _ = binary;
    Box::pin(async { Vec::new() })
}

pub const QWEN: RuntimeDefinition = RuntimeDefinition {
    id: "qwen",
    name: "Qwen",
    description: "Qwen coding CLI",
    binary: "qwen",
    fallback_binaries: &[],
    path_env_var: "DINGDA_QWEN_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::Plain,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        prompt_via_stdin: false,
    },
    install_url: "https://github.com/QwenLM/qwen-code",
    docs_url: "https://qwenlm.github.io/qwen-code-docs/en/index",
    external_mcp_injection: None,
    is_default: false,
    build_args: empty_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
