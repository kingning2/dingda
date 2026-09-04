use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::empty_args;
use crate::runtime::model_discover::{discover_acp_models, AcpDiscoveryConfig};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover_acp_models(binary, AcpDiscoveryConfig::default()))
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
        supports_resume: false,
        prompt_via_stdin: true,
    },
    install_url: "https://mimo.ai",
    docs_url: "https://mimo.ai/docs",
    external_mcp_injection: Some("mimo-env-content"),
    is_default: false,
    build_args: empty_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
