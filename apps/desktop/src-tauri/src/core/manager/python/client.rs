//! Sidecar 共享内存客户端（Rust → Python）— 归属 Python Runtime 生命周期层。
//!
//! 对外 API（[`SidecarClient::post_json`] / `get_json` / `get_text` /
//! `health_check`）与原 HTTP 实现保持一致，业务调用点无需改动；
//! 传输层已替换为共享内存邮箱（见 [`super::shm`]）。

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::json;

use super::shm::{ShmTransport, ShmTransportError};

#[derive(Debug, thiserror::Error)]
pub enum SidecarClientError {
    #[error("transport: {0}")]
    Transport(String),
    #[error("sidecar: {0}")]
    Sidecar(String),
}

impl From<ShmTransportError> for SidecarClientError {
    fn from(value: ShmTransportError) -> Self {
        match value {
            ShmTransportError::SidecarRestarted => Self::Transport(value.to_string()),
            other => Self::Transport(other.to_string()),
        }
    }
}

/// 高频探测/轮询路径：正常且够快时只打 DEBUG。
const QUIET_PATHS: &[&str] = &[
    "/health",
    "/v1/agent/ping",
    "/v1/channel/qr_check",
    "/v1/runtime/status",
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

/// 本地 Python Sidecar 共享内存客户端；段文件在首次使用时创建，
/// 路径经 `--shm` 参数传给 Python 进程。构造永不失败（懒初始化），
/// 共享内存段不可用时在首次调用/健康检查时返回错误。
#[derive(Clone)]
pub struct SidecarClient {
    shm_path: PathBuf,
    transport: Arc<Mutex<Option<ShmTransport>>>,
}

impl SidecarClient {
    /// 构建客户端（仅保存段路径，实际建段延迟到首次使用）。
    pub fn new(shm_path: &Path) -> Self {
        Self {
            shm_path: shm_path.to_path_buf(),
            transport: Arc::new(Mutex::new(None)),
        }
    }

    /// 共享内存段文件路径。
    pub fn shm_path(&self) -> &Path {
        &self.shm_path
    }

    /// 获取（或首次创建）共享内存传输端点。创建失败会在重试时再次尝试。
    fn transport(&self) -> Result<ShmTransport, SidecarClientError> {
        let mut guard = self.transport.lock().map_err(|error| {
            SidecarClientError::Transport(format!("shm transport lock: {error}"))
        })?;
        if guard.is_none() {
            *guard = Some(ShmTransport::create(&self.shm_path).map_err(SidecarClientError::from)?);
        }
        Ok(guard.as_ref().expect("lazy initialized").clone())
    }

    /// 健康检查：读取协议头 ready 标志与心跳时间戳，无请求往返。
    pub async fn health_check(&self) -> Result<bool, SidecarClientError> {
        let transport = self.transport()?;
        Ok(transport.is_healthy())
    }

    async fn call(
        &self,
        method: &str,
        path: &str,
        body: Option<serde_json::Value>,
    ) -> Result<(u32, serde_json::Value), SidecarClientError> {
        let envelope = json!({ "method": method, "path": path, "body": body });
        let payload = serde_json::to_vec(&envelope)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))?;
        let started = Instant::now();
        let transport = self.transport()?;
        let result =
            tauri::async_runtime::spawn_blocking(move || transport.call_blocking(&payload))
                .await
                .map_err(|error| SidecarClientError::Transport(error.to_string()))?;

        let label = sidecar_path_label(path);
        let duration_ms = started.elapsed().as_millis();
        match &result {
            Ok(_) => {
                let quiet = QUIET_PATHS.contains(&path) && duration_ms < QUIET_SLOW_MS;
                if quiet {
                    tracing::debug!(method, command = label, duration_ms, "Sidecar 调用完成");
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

        let response = result?;
        if response.status != 200 && response.status != 201 {
            return Err(SidecarClientError::Sidecar(format!(
                "unexpected status {}",
                response.status
            )));
        }
        let value = serde_json::from_slice(&response.body)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))?;
        Ok((response.status, value))
    }

    pub async fn get_json<Res>(&self, path: &str) -> Result<Res, SidecarClientError>
    where
        Res: DeserializeOwned,
    {
        let (_status, value) = self.call("GET", path, None).await?;
        serde_json::from_value(value)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))
    }

    pub async fn get_text(&self, path: &str) -> Result<String, SidecarClientError> {
        let envelope = json!({ "method": "GET", "path": path, "body": serde_json::Value::Null });
        let payload = serde_json::to_vec(&envelope)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))?;
        let transport = self.transport()?;
        let result =
            tauri::async_runtime::spawn_blocking(move || transport.call_blocking(&payload))
                .await
                .map_err(|error| SidecarClientError::Transport(error.to_string()))??;
        if result.status != 200 {
            return Err(SidecarClientError::Sidecar(format!(
                "unexpected status {}",
                result.status
            )));
        }
        Ok(String::from_utf8_lossy(&result.body).into_owned())
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
        let (_status, response) = self.call("POST", path, Some(value)).await?;
        serde_json::from_value(response)
            .map_err(|error| SidecarClientError::Transport(error.to_string()))
    }
}
