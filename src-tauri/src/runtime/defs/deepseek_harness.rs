use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::dsh_stdio_args;
use super::validate::validate_dsh_executable;
use crate::runtime::model_discover::discover_dsh_models;
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover_dsh_models(binary))
}

pub const DEEPSEEK_HARNESS: RuntimeDefinition = RuntimeDefinition {
    id: "deepseek-harness",
    name: "DeepSeek Harness",
    description: "DeepSeek native harness CLI",
    binary: "dsh",
    fallback_binaries: &[],
    path_env_var: "DINGDA_DSH_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::DshProfileJsonl,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: true,
        supports_images: false,
        prompt_via_stdin: true,
    },
    install_url: "https://www.deepseek.com/harness/en/",
    docs_url: "https://github.com/deepseek-ai/deepseek-harness",
    external_mcp_injection: None,
    is_default: false,
    build_args: dsh_stdio_args,
    validate_executable: Some(validate_dsh_executable),
    auth_probe_args: None,
    discover_models,
};
