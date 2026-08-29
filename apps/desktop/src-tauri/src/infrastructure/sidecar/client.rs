//! Sidecar 客户端 — 业务经 pipe ``sidecar.invoke``，Event 推送同管道。
//!
//! 对外 API（[`SidecarClient::post_json`] / `get_json` / `get_text` /
//! `health_check` / `request`）保持稳定。SHM 仅预留（[`Self::prepare_shm`]），
//! 产品路径不创建、不唤醒。

use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::{json, Value};
use tokio::sync::Mutex;

use super::connection::shm::{ShmTransport, ShmTransportError};
use super::connection::{IpcEndpoint, IpcError, IpcSession};

#[derive(Debug, thiserror::Error)]
pub enum SidecarClientError {
    #[error("transport: {0}")]
    Transport(String),
    #[error("sidecar: {0}")]
    Sidecar(String),
}

impl From<IpcError> for SidecarClientError {
    fn from(value: IpcError) -> Self {
        match value {
            IpcError::RpcFailed(msg) => Self::Sidecar(msg),
            other => Self::Transport(other.to_string()),
        }
    }
}

impl From<ShmTransportError> for SidecarClientError {
    fn from(value: ShmTransportError) -> Self {
        Self::Transport(value.to_string())
    }
}

/// 高频探测路径：正常且够快时不打 INFO/DEBUG（仅 TRACE）。
const QUIET_PATHS: &[&str] = &[
    "/health",
    "/v1/agent/ping",
    "/v1/agent/run/status",
    "/v1/channel/qr_check",
    "/v1/runtime/status",
    "/v1/ws/events/poll",
];
const QUIET_SLOW_MS: u128 = 500;

fn sidecar_path_label(path: &str) -> &'static str {
    match path {
        "/health" => "Sidecar 健康检查",
        "/v1/runtime/status" => "Sidecar 运行时快照",
        "/v1/agent/ping" => "Sidecar Agent 探活",
        "/v1/agent/reply" => "Sidecar Agent 对话",
        "/v1/agent/complete" => "Sidecar Agent 补全",
        "/v1/agent/run/start" => "Sidecar Agent Run 启动",
        "/v1/agent/run/control" => "Sidecar Agent Run 控制",
        "/v1/agent/run/status" => "Sidecar Agent Run 状态",
        "/v1/agent/run/cancel" => "Sidecar Agent Run 取消",
        "/v1/channel/qr_start" => "Sidecar 发起扫码",
        "/v1/channel/qr_check" => "Sidecar 检查扫码",
        "/v1/channel/qr_cancel" => "Sidecar 取消扫码",
        "/v1/channel/cookie_renew" => "Sidecar 浏览器续期 Cookie",
        "/v1/ws/connect" => "Sidecar WSS 连接",
        "/v1/ws/events/poll" => "Sidecar WSS 事件轮询(兼容)",
        _ => "Sidecar 未命名调用",
    }
}

/// 从请求体抽简短入参摘要，避免日志只剩「调用完成」却看不到 action/user。
fn sidecar_body_summary(path: &str, body: &Option<Value>) -> String {
    let Some(Value::Object(map)) = body else {
        return String::new();
    };
    let get = |key: &str| {
        map.get(key)
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string)
    };
    match path {
        "/v1/agent/run/start" => {
            let user = get("user").unwrap_or_default();
            let user_preview: String = user.chars().take(80).collect();
            let run_id = get("run_id").unwrap_or_default();
            let resume = get("resume_node").unwrap_or_else(|| "-".into());
            format!(" run_id={run_id} resume_node={resume} user={user_preview}")
        }
        "/v1/agent/run/control" => {
            let run_id = get("run_id").unwrap_or_default();
            let action = get("action").unwrap_or_default();
            let node = get("node").unwrap_or_else(|| "-".into());
            format!(" run_id={run_id} action={action} node={node}")
        }
        "/v1/agent/run/cancel" => {
            let run_id = get("run_id").unwrap_or_default();
            format!(" run_id={run_id}")
        }
        _ => String::new(),
    }
}

/// 本地 Python Sidecar 客户端；产品路径为 pipe RPC。
#[derive(Clone)]
pub struct SidecarClient {
    endpoint: IpcEndpoint,
    /// 预留大文件 SHM 路径（产品不创建）。
    shm_path: PathBuf,
    shm: Arc<Mutex<Option<ShmTransport>>>,
    session: Arc<Mutex<Option<IpcSession>>>,
}

impl SidecarClient {
    /// 构建客户端（不立即连线）。
    #[must_use]
    pub fn new(endpoint: IpcEndpoint, shm_path: PathBuf) -> Self {
        Self {
            endpoint,
            shm_path,
            shm: Arc::new(Mutex::new(None)),
            session: Arc::new(Mutex::new(None)),
        }
    }

    #[must_use]
    pub fn endpoint(&self) -> &IpcEndpoint {
        &self.endpoint
    }

    #[must_use]
    pub fn shm_path(&self) -> &Path {
        &self.shm_path
    }

    /// 创建（或重建）共享内存段 — 仅预留大文件路径使用。
    pub async fn prepare_shm(&self) -> Result<(), SidecarClientError> {
        let path = self.shm_path.clone();
        let transport = tokio::task::spawn_blocking(move || ShmTransport::create(&path))
            .await
            .map_err(|error| SidecarClientError::Transport(error.to_string()))??;
        *self.shm.lock().await = Some(transport);
        Ok(())
    }

    /// 建立管道并等待 Python `runtime.ready`。
    pub async fn connect(&self) -> Result<(), SidecarClientError> {
        let session = IpcSession::connect(&self.endpoint).await?;
        *self.session.lock().await = Some(session);
        Ok(())
    }

    /// 断开管道会话（幂等）。
    pub async fn disconnect(&self) -> Result<(), SidecarClientError> {
        let session = self.session.lock().await.take();
        if let Some(session) = session {
            session.shutdown().await?;
        }
        Ok(())
    }

    async fn session(&self) -> Result<IpcSession, SidecarClientError> {
        self.session
            .lock()
            .await
            .clone()
            .filter(|s| s.is_ready())
            .ok_or_else(|| SidecarClientError::Transport("IPC session not connected".into()))
    }

    /// 订阅 Python → Rust 控制面 Event（如 `runtime.ready` / `ws.event`）。
    pub async fn subscribe_events(
        &self,
    ) -> Result<tokio::sync::broadcast::Receiver<super::connection::RpcEvent>, SidecarClientError>
    {
        Ok(self.session().await?.subscribe_events())
    }

    /// 控制面 RPC（如 `runtime.ping`）。
    pub async fn request(&self, method: &str, params: Value) -> Result<Value, SidecarClientError> {
        let session = self.session().await?;
        Ok(session.request(method, params).await?)
    }

    /// 健康检查：管道会话就绪 + `runtime.ping`。
    pub async fn health_check(&self) -> Result<bool, SidecarClientError> {
        let Ok(session) = self.session().await else {
            return Ok(false);
        };
        if !session.is_ready() {
            return Ok(false);
        }
        match session.request("runtime.ping", json!({})).await {
            Ok(value) => Ok(value.get("pong").and_then(Value::as_bool).unwrap_or(false)),
            Err(_) => Ok(false),
        }
    }

    async fn invoke_path(
        &self,
        method: &str,
        path: &str,
        body: Option<Value>,
    ) -> Result<(u32, Value), SidecarClientError> {
        let started = Instant::now();
        let session = self.session().await?;
        let envelope = json!({
            "method": method,
            "path": path,
            "body": body,
        });

        let label = sidecar_path_label(path);
        let summary = sidecar_body_summary(path, &body);
        let result = session.request("sidecar.invoke", envelope).await;

        let duration_ms = started.elapsed().as_millis();
        match &result {
            Ok(_) => {
                let quiet = QUIET_PATHS.contains(&path) && duration_ms < QUIET_SLOW_MS;
                if quiet {
                    tracing::trace!(
                        method,
                        command = label,
                        duration_ms,
                        summary = %summary,
                        "Sidecar 调用完成"
                    );
                } else {
                    tracing::info!(
                        method,
                        command = label,
                        duration_ms,
                        "Sidecar 调用完成{summary}"
                    );
                }
            }
            Err(error) => {
                tracing::warn!(
                    method,
                    command = label,
                    duration_ms,
                    summary = %summary,
                    error = %error,
                    "Sidecar 调用失败"
                );
            }
        }

        let value = result?;
        let status = value.get("status").and_then(Value::as_u64).unwrap_or(500) as u32;
        if status != 200 && status != 201 {
            return Err(SidecarClientError::Sidecar(format!(
                "unexpected status {status}"
            )));
        }
        let body = value.get("body").cloned().unwrap_or(Value::Null);
        Ok((status, body))
    }

    pub async fn get_json<Res>(&self, path: &str) -> Result<Res, SidecarClientError>
    where
        Res: DeserializeOwned,
    {
        let (_status, value) = self.invoke_path("GET", path, None).await?;
        serde_json::from_value(value)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))
    }

    pub async fn get_text(&self, path: &str) -> Result<String, SidecarClientError> {
        let (_status, value) = self.invoke_path("GET", path, None).await?;
        match value {
            Value::String(s) => Ok(s),
            other => Ok(other.to_string()),
        }
    }

    pub async fn post_json<Req, Res>(
        &self,
        path: &str,
        body: &Req,
    ) -> Result<Res, SidecarClientError>
    where
        Req: Serialize + ?Sized,
        Res: DeserializeOwned,
    {
        let value = serde_json::to_value(body)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))?;
        let (_status, response) = self.invoke_path("POST", path, Some(value)).await?;
        serde_json::from_value(response)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))
    }
}

/// Python Sidecar IPC 面 — 暴露类型化 HTTP 客户端。
///
/// 业务 IPC 命令仍经 `AppState.lifecycle.client()` 获取同一客户端；
/// 本模块把 IPC 面收敛到 Python Runtime，供运行时层自用。
pub struct PythonIpc {
    client: SidecarClient,
}

impl PythonIpc {
    /// 用现有 Sidecar 客户端组装 IPC 面。
    #[allow(clippy::new_without_default)]
    pub fn new(client: SidecarClient) -> Self {
        Self { client }
    }

    /// 底层 Sidecar 客户端。
    pub fn client(&self) -> &SidecarClient {
        &self.client
    }
}
