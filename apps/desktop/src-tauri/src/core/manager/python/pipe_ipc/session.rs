//! IPC Session — 长连接多路 RPC + Event 分发。

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Duration;

use serde_json::{json, Value};
use tokio::io::AsyncWriteExt;
use tokio::sync::{broadcast, oneshot, Mutex};
use tokio::task::JoinHandle;

use super::endpoint::IpcEndpoint;
use super::error::IpcError;
use super::framing::{read_frame, write_frame};
use super::protocol::{RpcEvent, RpcResponse, WireMessage};
use super::transport::{connect_with_retry, ConnectedStream};

/// 默认单次 RPC 超时。
pub fn call_timeout() -> Duration {
    std::env::var("DINGDA_SIDECAR_CALL_TIMEOUT_MS")
        .ok()
        .and_then(|v| v.parse().ok())
        .map(Duration::from_millis)
        .unwrap_or(Duration::from_secs(30))
}

struct SessionInner {
    writer: Mutex<Box<dyn tokio::io::AsyncWrite + Unpin + Send>>,
    pending: Mutex<HashMap<u64, oneshot::Sender<RpcResponse>>>,
    next_id: AtomicU64,
    ready: AtomicBool,
    closed: AtomicBool,
    events_tx: broadcast::Sender<RpcEvent>,
    reader_task: Mutex<Option<JoinHandle<()>>>,
}

/// 已连接的 IPC 会话（可 Clone，共享同一条长连接）。
#[derive(Clone)]
pub struct IpcSession {
    inner: Arc<SessionInner>,
}

impl IpcSession {
    /// 连接 Python 监听端点，启动读循环，并等待 `runtime.ready` 事件。
    pub async fn connect(endpoint: &IpcEndpoint) -> Result<Self, IpcError> {
        let ConnectedStream { reader, writer } = connect_with_retry(endpoint, 80, 50).await?;

        let (events_tx, _) = broadcast::channel(64);
        let inner = Arc::new(SessionInner {
            writer: Mutex::new(writer),
            pending: Mutex::new(HashMap::new()),
            next_id: AtomicU64::new(1),
            ready: AtomicBool::new(false),
            closed: AtomicBool::new(false),
            events_tx: events_tx.clone(),
            reader_task: Mutex::new(None),
        });

        let session = Self {
            inner: inner.clone(),
        };
        let reader_inner = inner.clone();
        let handle = tokio::spawn(async move {
            reader_loop(reader_inner, reader).await;
        });
        *session.inner.reader_task.lock().await = Some(handle);

        session.wait_ready(Duration::from_secs(15)).await?;
        Ok(session)
    }

    async fn wait_ready(&self, timeout: Duration) -> Result<(), IpcError> {
        let mut rx = self.inner.events_tx.subscribe();
        if self.inner.ready.load(Ordering::Acquire) {
            return Ok(());
        }
        let deadline = tokio::time::Instant::now() + timeout;
        loop {
            let left = deadline.saturating_duration_since(tokio::time::Instant::now());
            if left.is_zero() {
                return Err(IpcError::Timeout(timeout));
            }
            match tokio::time::timeout(left, rx.recv()).await {
                Ok(Ok(ev)) if ev.method == "runtime.ready" => {
                    self.inner.ready.store(true, Ordering::Release);
                    return Ok(());
                }
                Ok(Ok(_)) => continue,
                Ok(Err(_)) => {
                    if self.inner.closed.load(Ordering::Acquire) {
                        return Err(IpcError::TransportClosed);
                    }
                    continue;
                }
                Err(_) => return Err(IpcError::Timeout(timeout)),
            }
        }
    }

    #[must_use]
    pub fn is_ready(&self) -> bool {
        self.inner.ready.load(Ordering::Acquire) && !self.inner.closed.load(Ordering::Acquire)
    }

    /// 订阅 Python → Rust 事件。
    pub fn subscribe_events(&self) -> broadcast::Receiver<RpcEvent> {
        self.inner.events_tx.subscribe()
    }

    /// 发送 RPC 并等待匹配 `id` 的响应。
    pub async fn request(&self, method: &str, params: Value) -> Result<Value, IpcError> {
        if self.inner.closed.load(Ordering::Acquire) {
            return Err(IpcError::TransportClosed);
        }
        if !self.inner.ready.load(Ordering::Acquire) && method != "runtime.shutdown" {
            return Err(IpcError::RuntimeUnavailable("sidecar not ready".into()));
        }

        let id = self.inner.next_id.fetch_add(1, Ordering::Relaxed);
        let (tx, rx) = oneshot::channel();
        {
            let mut pending = self.inner.pending.lock().await;
            pending.insert(id, tx);
        }

        let msg = WireMessage::Request {
            id,
            method: method.to_string(),
            params,
        };
        let bytes = msg.encode().map_err(IpcError::ProtocolError)?;
        {
            let mut writer = self.inner.writer.lock().await;
            if let Err(err) = write_frame(&mut *writer, &bytes).await {
                let mut pending = self.inner.pending.lock().await;
                pending.remove(&id);
                return Err(err);
            }
        }

        match tokio::time::timeout(call_timeout(), rx).await {
            Ok(Ok(resp)) => {
                if resp.success {
                    Ok(resp.result.unwrap_or(Value::Null))
                } else {
                    let msg = resp
                        .error
                        .map(|e| format!("{}: {}", e.code, e.message))
                        .unwrap_or_else(|| "rpc failed".into());
                    Err(IpcError::RpcFailed(msg))
                }
            }
            Ok(Err(_)) => Err(IpcError::TransportClosed),
            Err(_) => {
                let mut pending = self.inner.pending.lock().await;
                pending.remove(&id);
                Err(IpcError::Timeout(call_timeout()))
            }
        }
    }

    /// 优雅关闭：尽力通知 Python 后断开。
    pub async fn shutdown(&self) -> Result<(), IpcError> {
        if self.inner.closed.swap(true, Ordering::AcqRel) {
            return Ok(());
        }
        let id = self.inner.next_id.fetch_add(1, Ordering::Relaxed);
        let msg = WireMessage::Request {
            id,
            method: "runtime.shutdown".into(),
            params: json!({}),
        };
        if let Ok(bytes) = msg.encode() {
            let mut writer = self.inner.writer.lock().await;
            let _ = write_frame(&mut *writer, &bytes).await;
            let _ = writer.shutdown().await;
        }
        if let Some(handle) = self.inner.reader_task.lock().await.take() {
            handle.abort();
        }
        self.inner.pending.lock().await.clear();
        Ok(())
    }
}

async fn reader_loop(
    inner: Arc<SessionInner>,
    mut reader: Box<dyn tokio::io::AsyncRead + Unpin + Send>,
) {
    loop {
        match read_frame(&mut reader).await {
            Ok(bytes) => match WireMessage::decode(&bytes) {
                Ok(WireMessage::Response {
                    id,
                    success,
                    result,
                    error,
                }) => {
                    let resp = RpcResponse {
                        id,
                        success,
                        result,
                        error,
                    };
                    let mut pending = inner.pending.lock().await;
                    if let Some(tx) = pending.remove(&id) {
                        let _ = tx.send(resp);
                    }
                }
                Ok(WireMessage::Event { method, params }) => {
                    if method == "runtime.ready" {
                        inner.ready.store(true, Ordering::Release);
                    }
                    let _ = inner.events_tx.send(RpcEvent { method, params });
                }
                Ok(WireMessage::Request { .. }) => {}
                Err(err) => {
                    tracing::warn!(error = %err, "IPC protocol decode failed");
                }
            },
            Err(IpcError::TransportClosed) => {
                inner.closed.store(true, Ordering::Release);
                inner.pending.lock().await.clear();
                break;
            }
            Err(err) => {
                tracing::warn!(error = %err, "IPC read failed");
                inner.closed.store(true, Ordering::Release);
                inner.pending.lock().await.clear();
                break;
            }
        }
    }
}
