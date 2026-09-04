use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::empty_args;
use crate::runtime::model_discover::{parse_pi_models, run_command};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    if let Ok(stdout) = run_command(binary, &["--list-models"]).await {
        let parsed = parse_pi_models(&stdout);
        if !parsed.is_empty() {
            return parsed;
        }
    }
    Vec::new()
}

pub const PI: RuntimeDefinition = RuntimeDefinition {
    id: "pi",
    name: "Pi",
    description: "Inflection chat CLI",
    binary: "pi",
    fallback_binaries: &[],
    path_env_var: "DINGDA_PI_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::PiRpc,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: true,
        prompt_via_stdin: true,
    },
    install_url: "https://github.com/nexu-io/open-design/blob/main/docs/agent-adapters.md",
    docs_url: "https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md",
    external_mcp_injection: None,
    is_default: false,
    build_args: empty_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
