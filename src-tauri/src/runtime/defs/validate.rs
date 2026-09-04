use std::path::Path;
use std::process::Stdio;

pub fn validate_dsh_executable(executable: &Path) -> bool {
    let Ok(output) = std::process::Command::new(executable)
        .args(["--profile", "multica", "--probe"])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
    else {
        return false;
    };

    if !output.status.success() {
        return false;
    }

    for line in String::from_utf8_lossy(&output.stdout).lines() {
        let Ok(frame) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        if frame.get("v").and_then(|v| v.as_i64()) == Some(1)
            && frame.get("type").and_then(|v| v.as_str()) == Some("probe")
            && frame.get("runtime").and_then(|v| v.as_str()) == Some("dsh")
            && frame.get("protocol_version").and_then(|v| v.as_i64()) == Some(1)
        {
            return true;
        }
    }
    false
}
