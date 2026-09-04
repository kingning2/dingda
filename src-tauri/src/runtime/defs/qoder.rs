use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::empty_args;
use crate::runtime::model_discover::{discover_acp_models, AcpDiscoveryConfig};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    discover_acp_models(
        binary,
        AcpDiscoveryConfig::with_args(&["--yolo", "--acp"]),
    )
    .await
}

pub const QODER: RuntimeDefinition = RuntimeDefinition {
    id: "qoder",
    name: "Qoder",
    description: "Alibaba coding CLI",
    binary: "qodercli",
    fallback_binaries: &[],
    path_env_var: "DINGDA_QODER_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::QoderStreamJson,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        prompt_via_stdin: true,
    },
    install_url: "https://qoder.com/download",
    docs_url: "https://docs.qoder.com",
    external_mcp_injection: None,
    is_default: false,
    build_args: empty_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
