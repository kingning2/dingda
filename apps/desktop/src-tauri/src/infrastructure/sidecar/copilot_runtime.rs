//! 副驾 pipe 事件监听 — `copilot.run` → Tauri `app/copilot/agui`。

use std::sync::Arc;
use std::time::Duration;

use tauri::{AppHandle, Emitter};
use tokio::sync::broadcast::error::RecvError;
use tracing::{info, warn};

use crate::infrastructure::sidecar::SidecarClient;

pub const COPILOT_RUN_EVENT: &str = "copilot.run";
pub const COPILOT_AGUI_TOPIC: &str = "app/copilot/agui";

const RUNTIME_TARGET: &str = "runtime";

/// 全局订阅 pipe `copilot.run`，转发 AG-UI 事件到前端。
pub fn spawn_copilot_pipe_listener(client: SidecarClient, app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        loop {
            let mut rx = match client.subscribe_events().await {
                Ok(rx) => rx,
                Err(error) => {
                    warn!(
                        target: RUNTIME_TARGET,
                        %error,
                        "[runtime] copilot.run.subscribe.failed"
                    );
                    tokio::time::sleep(Duration::from_secs(1)).await;
                    continue;
                }
            };
            info!(target: RUNTIME_TARGET, "[runtime] copilot.run.subscribe");
            loop {
                match rx.recv().await {
                    Ok(event) => {
                        if event.method != COPILOT_RUN_EVENT {
                            continue;
                        }
                        if let Err(error) = app.emit(COPILOT_AGUI_TOPIC, event.params) {
                            warn!(
                                target: RUNTIME_TARGET,
                                %error,
                                "[runtime] copilot.run.emit.failed"
                            );
                        }
                    }
                    Err(RecvError::Lagged(_)) => {
                        warn!(target: RUNTIME_TARGET, "[runtime] copilot.run.lagged");
                    }
                    Err(RecvError::Closed) => {
                        warn!(target: RUNTIME_TARGET, "[runtime] copilot.run.closed");
                        break;
                    }
                }
            }
        }
    });
}

/// 启动副驾 pipe 监听（与 AgentRuntime 解耦，仅需 SidecarClient）。
pub fn spawn_copilot_pipe_listener_from_lifecycle(
    lifecycle: Arc<crate::infrastructure::sidecar::SidecarLifecycle>,
    app: AppHandle,
) {
    let client = lifecycle.client().clone();
    spawn_copilot_pipe_listener(client, app);
}
