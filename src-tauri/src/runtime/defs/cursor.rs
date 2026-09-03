use std::future::Future;
use std::path::Path;
use std::pin::Pin;

use super::build_args::cursor_build_args;
use crate::runtime::model_discover::{parse_cursor_models, run_command};
use crate::runtime::types::{RuntimeCapabilities, RuntimeDefinition, RuntimeModel, StreamFormat};

pub fn discover_models(
    binary: &Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + '_>> {
    Box::pin(discover(binary))
}

async fn discover(binary: &Path) -> Vec<RuntimeModel> {
    if let Ok(stdout) = run_command(binary, &["--list-models"]).await {
        let parsed = parse_cursor_models(&stdout);
        if !parsed.is_empty() {
            return parsed;
        }
    }
    vec![RuntimeModel {
        id: "auto".to_string(),
        label: "Auto".to_string(),
    }]
}

pub const CURSOR: RuntimeDefinition = RuntimeDefinition {
    id: "cursor-agent",
    name: "Cursor",
    description: "Cursor command line",
    binary: "cursor-agent",
    fallback_binaries: &["agent"],
    path_env_var: "DINGDA_CURSOR_PATH",
    version_args: &["--version"],
    stream_format: StreamFormat::JsonEventStream,
    capabilities: RuntimeCapabilities {
        login_capable: false,
        supports_resume: false,
        supports_images: false,
        prompt_via_stdin: true,
    },
    install_url: "https://cursor.com/docs/cli/overview",
    docs_url: "https://docs.cursor.com/en/cli/overview",
    external_mcp_injection: None,
    is_default: false,
    build_args: cursor_build_args,
    validate_executable: None,
    auth_probe_args: None,
    discover_models,
};
