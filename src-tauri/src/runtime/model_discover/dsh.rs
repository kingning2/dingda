use std::path::Path;

use serde::Deserialize;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::time::{timeout, Duration};

use crate::runtime::types::RuntimeModel;

const DSH_PROFILE: &str = "multica";
const DSH_TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Debug, Deserialize)]
struct DshFrame {
    v: Option<i64>,
    #[serde(rename = "type")]
    frame_type: Option<String>,
    models: Option<Vec<DshModelFrame>>,
}

#[derive(Debug, Deserialize)]
struct DshModelFrame {
    id: String,
    label: String,
    #[serde(default)]
    #[allow(dead_code)]
    provider: Option<String>,
    #[serde(default)]
    default: bool,
}

pub async fn discover_dsh_models(binary: &Path) -> Vec<RuntimeModel> {
    let binary = binary.to_path_buf();
    let result = timeout(DSH_TIMEOUT, run_dsh_list_models(binary)).await;
    match result {
        Ok(Ok(models)) if !models.is_empty() => models,
        _ => Vec::new(),
    }
}

async fn run_dsh_list_models(binary: std::path::PathBuf) -> Result<Vec<RuntimeModel>, ()> {
    let mut child = Command::new(&binary)
        .args(["--profile", DSH_PROFILE, "--list-models"])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .map_err(|_| ())?;

    let stdout = child.stdout.take().ok_or(())?;
    let mut reader = BufReader::new(stdout);
    let mut line = String::new();
    let mut models = Vec::new();

    loop {
        line.clear();
        let read = reader.read_line(&mut line).await.map_err(|_| ())?;
        if read == 0 {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let frame: DshFrame = match serde_json::from_str(trimmed) {
            Ok(frame) => frame,
            Err(_) => continue,
        };
        if frame.v != Some(1) || frame.frame_type.as_deref() != Some("models") {
            continue;
        }
        if let Some(items) = frame.models {
            for item in items {
                if item.id.trim().is_empty() {
                    continue;
                }
                let mut label = item.label.trim().to_string();
                if label.is_empty() {
                    label = item.id.clone();
                }
                if item.default {
                    label = format!("{label} (default)");
                }
                models.push(RuntimeModel {
                    id: item.id,
                    label,
                });
            }
        }
    }

    let status = child.wait().await.map_err(|_| ())?;
    if !status.success() && models.is_empty() {
        return Err(());
    }
    Ok(models)
}
