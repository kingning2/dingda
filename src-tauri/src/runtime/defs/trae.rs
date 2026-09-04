use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::acp_serve_args;
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
        AcpDiscoveryConfig::with_args(&["acp", "serve", "--yolo"]),
    )
    .await
}

pub const TRAE: RuntimeDefinition = RuntimeDefinition {
    id: "trae-cli",
    name: "Trae CLI",
    description: "ByteDance Trae agent CLI",
    binary: "traecli",
    fallback_binaries: &[],
    path_env_var: "DINGDA_TRAECLI_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::AcpJsonRpc,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        prompt_via_stdin: true,
    },
    install_url: "https://www.volcengine.com/docs/86677/2227861?lang=zh",
    docs_url: "https://www.volcengine.com/docs/86677/2227861?lang=zh",
    external_mcp_injection: Some("acp-merge"),
    is_default: false,
    build_args: acp_serve_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
