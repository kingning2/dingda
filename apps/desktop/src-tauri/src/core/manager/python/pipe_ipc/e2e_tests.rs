//! IPC 端到端冒烟：spawn Python sidecar → connect → ping / concurrent / shutdown。
//!
//! 需要本机可用 `uv` 与 `python/` 目录。默认跳过；设 `DINGDA_IPC_E2E=1` 开启。

use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;

use serde_json::json;
use tokio::process::Command;
use tokio::time::timeout;

use crate::core::manager::python::pipe_ipc::{IpcEndpoint, IpcSession};

fn sidecar_dir() -> Option<PathBuf> {
    if let Ok(dir) = std::env::var("DINGDA_SIDECAR_DIR") {
        return Some(PathBuf::from(dir));
    }
    let mut dir = std::env::current_dir().ok()?;
    for _ in 0..8 {
        let candidate = dir.join("python");
        if candidate.join("pyproject.toml").is_file() {
            return Some(candidate);
        }
        if !dir.pop() {
            break;
        }
    }
    None
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn ipc_ping_concurrent_shutdown() {
    let Some(sidecar_dir) = sidecar_dir() else {
        eprintln!("skip: python sidecar dir not found");
        return;
    };
    if std::env::var("DINGDA_IPC_E2E").ok().as_deref() != Some("1") {
        // 默认跳过重型 e2e；本地/CI 设 DINGDA_IPC_E2E=1 开启。
        eprintln!("skip: set DINGDA_IPC_E2E=1 to run sidecar IPC e2e");
        return;
    }

    let endpoint = IpcEndpoint::for_pid(std::process::id().wrapping_add(4242));
    let ipc = endpoint.display();

    let mut child = Command::new("uv")
        .arg("run")
        .arg("--directory")
        .arg(&sidecar_dir)
        .arg("python")
        .arg("-m")
        .arg("sidecar.main")
        .arg("--ipc")
        .arg(&ipc)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()
        .expect("spawn python sidecar");

    let session = match timeout(Duration::from_secs(20), IpcSession::connect(&endpoint)).await {
        Ok(Ok(s)) => s,
        Ok(Err(err)) => {
            let _ = child.kill().await;
            panic!("IPC connect failed: {err}");
        }
        Err(_) => {
            let _ = child.kill().await;
            panic!("IPC connect timed out");
        }
    };

    let pong = session
        .request("runtime.ping", json!({}))
        .await
        .expect("ping");
    assert_eq!(pong.get("pong"), Some(&json!(true)));

    let mut handles = Vec::new();
    for i in 0..4 {
        let s = session.clone();
        handles.push(tokio::spawn(async move {
            s.request("runtime.ping", json!({ "n": i })).await
        }));
    }
    for handle in handles {
        let value = handle.await.expect("join").expect("concurrent ping");
        assert_eq!(value.get("pong"), Some(&json!(true)));
    }

    session.shutdown().await.expect("shutdown");
    let status = timeout(Duration::from_secs(5), child.wait())
        .await
        .expect("wait timeout")
        .expect("wait child");
    assert!(status.success() || status.code().is_some());
}
