//! Sidecar IPC 客户端（Rust → Python）— 长连接 Named Pipe / Unix Socket。
//!
//! 对外 API（[`SidecarClient::post_json`] / `get_json` / `get_text` /
//! `health_check` / `request`）保持稳定；传输层为 [`super::pipe_ipc`]。

use std::sync::Arc;
use std::time::Instant;

use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::{json, Value};
use tokio::sync::Mutex;

use super::pipe_ipc::{IpcEndpoint, IpcError, IpcSession};

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

/// 高频探测/轮询路径：正常且够快时不打 INFO/DEBUG（仅 TRACE）。
const QUIET_PATHS: &[&str] = &[
    "/health",
    "/v1/agent/ping",
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
        "/v1/channel/qr_start" => "Sidecar 发起扫码",
        "/v1/channel/qr_check" => "Sidecar 检查扫码",
        "/v1/channel/qr_cancel" => "Sidecar 取消扫码",
        "/v1/channel/cookie_renew" => "Sidecar 浏览器续期 Cookie",
        "/v1/ws/connect" => "Sidecar WSS 连接",
        "/v1/ws/events/poll" => "Sidecar WSS 事件轮询",
        _ => "Sidecar 未命名调用",
    }
}

/// 本地 Python Sidecar IPC 客户端；端点经 `--ipc` 传给 Python。
/// 构造仅保存端点，[`Self::connect`] 建立长连接并等待 `runtime.ready`。
#[derive(Clone)]
pub struct SidecarClient {
    endpoint: IpcEndpoint,
    session: Arc<Mutex<Option<IpcSession>>>,
}

impl SidecarClient {
    /// 构建客户端（不立即连线）。
    #[must_use]
    pub fn new(endpoint: IpcEndpoint) -> Self {
        Self {
            endpoint,
            session: Arc::new(Mutex::new(None)),
        }
    }

    #[must_use]
    pub fn endpoint(&self) -> &IpcEndpoint {
        &self.endpoint
    }

    /// 建立长连接并等待 Python `runtime.ready`。
    pub async fn connect(&self) -> Result<(), SidecarClientError> {
        let session = IpcSession::connect(&self.endpoint).await?;
        *self.session.lock().await = Some(session);
        Ok(())
    }

    /// 断开并清理会话（幂等）。
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

    /// 通用 RPC（业务可直接用 method 名，如 `runtime.ping`）。
    pub async fn request(&self, method: &str, params: Value) -> Result<Value, SidecarClientError> {
        let session = self.session().await?;
        Ok(session.request(method, params).await?)
    }

    /// 健康检查：会话就绪且 `runtime.ping` 成功。
    pub async fn health_check(&self) -> Result<bool, SidecarClientError> {
        let Ok(session) = self.session().await else {
            return Ok(false);
        };
        if !session.is_ready() {
            return Ok(false);
        }
        match session.request("runtime.ping", json!({})).await {
            Ok(_) => Ok(true),
            Err(IpcError::TransportClosed) | Err(IpcError::RuntimeUnavailable(_)) => Ok(false),
            Err(err) => Err(err.into()),
        }
    }

    async fn invoke_http(
        &self,
        method: &str,
        path: &str,
        body: Option<Value>,
    ) -> Result<(u32, Value), SidecarClientError> {
        let started = Instant::now();
        let result = self
            .request(
                "sidecar.invoke",
                json!({
                    "http_method": method,
                    "path": path,
                    "body": body,
                }),
            )
            .await;
        let label = sidecar_path_label(path);
        let duration_ms = started.elapsed().as_millis();
        match &result {
            Ok(_) => {
                let quiet = QUIET_PATHS.contains(&path) && duration_ms < QUIET_SLOW_MS;
                if quiet {
                    tracing::trace!(method, command = label, duration_ms, "Sidecar 调用完成");
                } else {
                    tracing::info!(method, command = label, duration_ms, "Sidecar 调用完成");
                }
            }
            Err(error) => {
                tracing::warn!(
                    method,
                    command = label,
                    duration_ms,
                    error = %error,
                    "Sidecar 调用失败"
                );
            }
        }
        let value = result?;
        let status = value.get("status").and_then(|v| v.as_u64()).unwrap_or(500) as u32;
        let body = value.get("body").cloned().unwrap_or(Value::Null);
        if status != 200 && status != 201 {
            return Err(SidecarClientError::Sidecar(format!(
                "unexpected status {status}"
            )));
        }
        Ok((status, body))
    }

    pub async fn get_json<Res>(&self, path: &str) -> Result<Res, SidecarClientError>
    where
        Res: DeserializeOwned,
    {
        let (_status, value) = self.invoke_http("GET", path, None).await?;
        serde_json::from_value(value)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))
    }

    pub async fn get_text(&self, path: &str) -> Result<String, SidecarClientError> {
        let (_status, value) = self.invoke_http("GET", path, None).await?;
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
        let (_status, response) = self.invoke_http("POST", path, Some(value)).await?;
        serde_json::from_value(response)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))
    }
}
