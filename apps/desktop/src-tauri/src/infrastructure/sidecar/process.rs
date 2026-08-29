//! Python 进程生命周期 — Sidecar 进程启动 / 健康 / 停止 / 重启。
//!
//! 经 `--ipc` 启动 Python：业务与 Event 均走管道；SHM 为预留大文件通道。

use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use super::client::SidecarClient;
use super::connection::IpcEndpoint;
use super::events;
use crate::contracts::{RuntimeEventError, RuntimeEventSidecarRestarted};
use crate::infrastructure::event::EventBus;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

pub const SIDECAR_RESTARTED_TOPIC: &str = "runtime/sidecar/restarted";
pub const RUNTIME_ERROR_TOPIC: &str = "runtime/error";

#[derive(Debug, thiserror::Error)]
pub enum SidecarLifecycleError {
    #[error("侧车目录不存在: {0}")]
    SidecarDirNotFound(String),
    #[error("启动侧车失败: {0}")]
    SpawnFailed(String),
    #[error("侧车启动超时（{0:?}）")]
    StartupTimeout(Duration),
    #[error("停止侧车失败: {0}")]
    StopFailed(String),
}

#[derive(Debug, Clone)]
pub struct SidecarConfig {
    pub port: u16,
    /// IPC 端点（Windows Named Pipe / Unix Domain Socket），经 `--ipc` 传给 Python。
    pub ipc_endpoint: IpcEndpoint,
    /// 预留大文件 SHM 路径（产品启动不传 `--shm`）。
    pub shm_path: PathBuf,
    pub sidecar_dir: PathBuf,
    pub use_uv: bool,
    pub python_executable: String,
    pub startup_timeout: Duration,
    pub max_restart_attempts: u32,
    /// Frozen sidecar executable (release / DINGDA_SIDECAR_BIN). When set, takes precedence over dev spawn.
    pub bundled_executable: Option<PathBuf>,
}

impl SidecarConfig {
    pub fn from_env() -> Self {
        let port = std::env::var("DINGDA_SIDECAR_PORT")
            .ok()
            .and_then(|value| value.parse().ok())
            .unwrap_or(8787);
        let max_restart_attempts = std::env::var("DINGDA_SIDECAR_MAX_RESTARTS")
            .ok()
            .and_then(|value| value.parse().ok())
            .unwrap_or(5);

        Self {
            port,
            ipc_endpoint: resolve_ipc_endpoint(),
            shm_path: resolve_shm_path(),
            sidecar_dir: resolve_sidecar_dir(),
            use_uv: std::env::var("DINGDA_USE_UV")
                .map(|value| value != "0")
                .unwrap_or(true),
            python_executable: std::env::var("DINGDA_PYTHON")
                .unwrap_or_else(|_| "python".to_string()),
            startup_timeout: Duration::from_secs(15),
            max_restart_attempts,
            bundled_executable: resolve_bundled_executable(),
        }
    }

    pub fn with_bundled_executable(mut self, path: PathBuf) -> Self {
        self.bundled_executable = Some(path);
        self
    }
}

pub struct SidecarLifecycle {
    config: SidecarConfig,
    client: SidecarClient,
    child: Mutex<Option<Child>>,
    /// 串行化 spawn / restart，防止并发 ensure_running 双开抢 Named Pipe。
    spawn_gate: Mutex<()>,
    event_bus: Arc<dyn EventBus>,
    ever_started: Mutex<bool>,
    restart_attempts: Mutex<u32>,
}

impl SidecarLifecycle {
    pub fn new(config: SidecarConfig, event_bus: Arc<dyn EventBus>) -> Self {
        let client = SidecarClient::new(config.ipc_endpoint.clone(), config.shm_path.clone());
        Self {
            config,
            client,
            child: Mutex::new(None),
            spawn_gate: Mutex::new(()),
            event_bus,
            ever_started: Mutex::new(false),
            restart_attempts: Mutex::new(0),
        }
    }

    pub fn client(&self) -> &SidecarClient {
        &self.client
    }

    /// 子进程是否已退出（退出即移除句柄，供 watchdog 触发重启）。
    pub async fn is_child_exited(&self) -> bool {
        self.child_exited().await
    }

    pub async fn ensure_running(&self) -> Result<(), SidecarLifecycleError> {
        let _gate = self.spawn_gate.lock().await;
        if self.child_exited().await {
            return self.restart_with_event("process exited").await;
        }
        if self.health_check().await? {
            return Ok(());
        }
        self.restart_with_event("health check failed").await
    }

    pub async fn health_check(&self) -> Result<bool, SidecarLifecycleError> {
        self.client
            .health_check()
            .await
            .map_err(|error| SidecarLifecycleError::SpawnFailed(error.to_string()))
    }

    /// 手动重启（用户/编排触发）：不累计 crash 退避，但发布重启事件。
    pub async fn restart(&self) -> Result<(), SidecarLifecycleError> {
        let _gate = self.spawn_gate.lock().await;
        let should_publish = *self.ever_started.lock().await;
        self.stop().await?;
        self.start_internal(true).await?;
        if should_publish {
            self.publish_restarted(0, "manual restart");
        }
        Ok(())
    }

    async fn restart_with_event(&self, reason: &str) -> Result<(), SidecarLifecycleError> {
        // 调用方须已持有 spawn_gate。
        let should_publish = *self.ever_started.lock().await;
        let attempt = {
            let mut attempts = self.restart_attempts.lock().await;
            *attempts += 1;
            *attempts
        };

        if attempt > self.config.max_restart_attempts {
            let err = SidecarLifecycleError::SpawnFailed(format!(
                "超过最大重启次数（{}）",
                self.config.max_restart_attempts
            ));
            self.publish_error("network", "restart", err.to_string());
            return Err(err);
        }

        // 指数退避，避免崩溃循环打满 CPU / 日志洪峰（上限 5s）。
        if attempt > 1 {
            let backoff_ms = 250_u64 * (1_u64 << (attempt.saturating_sub(1)).min(4));
            let backoff = Duration::from_millis(backoff_ms).min(Duration::from_secs(5));
            warn!(attempt, ?backoff, %reason, "侧车重启退避");
            tokio::time::sleep(backoff).await;
        }

        self.stop().await?;
        self.start_internal(true).await?;

        if should_publish {
            self.publish_restarted(attempt, reason);
        }
        Ok(())
    }

    pub async fn start(&self) -> Result<(), SidecarLifecycleError> {
        let _gate = self.spawn_gate.lock().await;
        if self.health_check().await? {
            // 启动日志由 Python 侧车（"侧车已启动"）输出，这里不重复打。
            *self.ever_started.lock().await = true;
            return Ok(());
        }
        self.start_internal(true).await
    }

    async fn start_internal(&self, track_child: bool) -> Result<(), SidecarLifecycleError> {
        {
            let guard = self.child.lock().await;
            if guard.is_some() {
                return self.wait_until_healthy().await;
            }
        }

        if self.config.bundled_executable.is_none() && !self.config.sidecar_dir.exists() {
            let err = SidecarLifecycleError::SidecarDirNotFound(
                self.config.sidecar_dir.display().to_string(),
            );
            self.publish_error("network", "startup", err.to_string());
            return Err(err);
        }

        let mut command = match build_spawn_command(&self.config) {
            Ok(command) => command,
            Err(err) => {
                self.publish_error("network", "startup", err.to_string());
                return Err(err);
            }
        };
        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                let err = SidecarLifecycleError::SpawnFailed(error.to_string());
                self.publish_error("network", "startup", err.to_string());
                return Err(err);
            }
        };

        if let Some(stdout) = child.stdout.take() {
            tokio::spawn(pipe_logs(stdout, "stdout"));
        }
        if let Some(stderr) = child.stderr.take() {
            tokio::spawn(pipe_logs(stderr, "stderr"));
        }

        // 启动日志由 Python 侧车输出，这里不重复打。
        if track_child {
            *self.child.lock().await = Some(child);
        }
        self.wait_until_healthy().await?;
        // 成功健康即清除重启计数，后续 crash 不再受旧闸门约束。
        *self.restart_attempts.lock().await = 0;
        *self.ever_started.lock().await = true;
        Ok(())
    }

    /// 停止 Sidecar：先断开 IPC / 通知 shutdown，宽限等待进程退出，超时再硬杀。
    pub async fn stop(&self) -> Result<(), SidecarLifecycleError> {
        let _ = tokio::time::timeout(Duration::from_secs(2), self.client().disconnect()).await;

        // 2. 宽限等待子进程退出（2s），未退出则 SIGKILL 兜底。
        let mut guard = self.child.lock().await;
        if let Some(mut child) = guard.take() {
            let deadline = Instant::now() + Duration::from_secs(2);
            let mut exited = false;
            loop {
                match child.try_wait() {
                    Ok(Some(_status)) => {
                        exited = true;
                        break;
                    }
                    Ok(None) => {}
                    Err(error) => {
                        warn!(%error, "侧车进程状态检查失败");
                        break;
                    }
                }
                if Instant::now() >= deadline {
                    break;
                }
                tokio::time::sleep(Duration::from_millis(50)).await;
            }
            if !exited {
                child
                    .kill()
                    .await
                    .map_err(|error| SidecarLifecycleError::StopFailed(error.to_string()))?;
                if let Err(error) = child.wait().await {
                    warn!(%error, "侧车进程停止后等待失败");
                }
            }
            info!("侧车进程已停止");
        }
        Ok(())
    }

    async fn child_exited(&self) -> bool {
        let mut guard = self.child.lock().await;
        let Some(child) = guard.as_mut() else {
            return false;
        };

        match child.try_wait() {
            Ok(Some(_status)) => {
                guard.take();
                true
            }
            Ok(None) => false,
            Err(error) => {
                warn!(%error, "侧车进程状态检查失败");
                false
            }
        }
    }

    fn publish_restarted(&self, attempt: u32, reason: &str) {
        let millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or(0);
        let payload = RuntimeEventSidecarRestarted {
            event_id: format!("evt-{millis}"),
            occurred_at: millis.to_string(),
            port: self.config.port as i64,
            attempt: attempt as i64,
            reason: Some(reason.to_string()),
        };

        let Ok(bytes) = serde_json::to_vec(&payload) else {
            warn!("侧车重启事件序列化失败");
            return;
        };

        if let Err(error) = self.event_bus.publish(SIDECAR_RESTARTED_TOPIC, &bytes) {
            warn!(%error, "侧车重启事件发布失败");
        }
    }

    /// 发布运行时错误事件（前端订阅标记后端不可用）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `kind` — 错误分类（`network` / `ipc` / `code`，Rust 侧恒为 `network`）
    /// - `stage` — 发生阶段（`startup` / `health` / `restart`）
    /// - `message` — 错误消息
    fn publish_error(&self, kind: &str, stage: &str, message: String) {
        let millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or(0);
        let payload = RuntimeEventError {
            event_id: format!("evt-{millis}"),
            occurred_at: millis.to_string(),
            kind: kind.to_string(),
            stage: Some(stage.to_string()),
            message,
            detail: None,
        };

        let Ok(bytes) = serde_json::to_vec(&payload) else {
            warn!("运行时错误事件序列化失败");
            return;
        };

        if let Err(error) = self.event_bus.publish(RUNTIME_ERROR_TOPIC, &bytes) {
            warn!(%error, "运行时错误事件发布失败");
        }
    }

    async fn wait_until_healthy(&self) -> Result<(), SidecarLifecycleError> {
        let deadline = Instant::now() + self.config.startup_timeout;
        // 先建立 IPC（Python 监听后 accept + runtime.ready），再 ping。
        while Instant::now() < deadline {
            match self.client.connect().await {
                Ok(()) => break,
                Err(err) => {
                    if Instant::now() >= deadline {
                        let _ = self.stop().await;
                        let timeout =
                            SidecarLifecycleError::StartupTimeout(self.config.startup_timeout);
                        self.publish_error("network", "startup", format!("{timeout}; last={err}"));
                        return Err(timeout);
                    }
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
            }
        }

        while Instant::now() < deadline {
            match self.health_check().await {
                Ok(true) => return Ok(()),
                Ok(false) => {}
                Err(err) => {
                    self.publish_error("network", "health", err.to_string());
                    return Err(err);
                }
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }

        let _ = self.stop().await;
        let err = SidecarLifecycleError::StartupTimeout(self.config.startup_timeout);
        self.publish_error("network", "startup", err.to_string());
        Err(err)
    }
}

fn resolve_sidecar_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("DINGDA_SIDECAR_DIR") {
        return PathBuf::from(dir);
    }

    if let Ok(mut dir) = std::env::current_dir() {
        for _ in 0..6 {
            let candidate = dir.join("python");
            if candidate.join("pyproject.toml").is_file() {
                return candidate;
            }
            if !dir.pop() {
                break;
            }
        }
    }

    PathBuf::from("python")
}

fn resolve_ipc_endpoint() -> IpcEndpoint {
    if let Ok(path) = std::env::var("DINGDA_SIDECAR_IPC") {
        return IpcEndpoint::from_path(path);
    }
    IpcEndpoint::for_pid(std::process::id())
}

fn resolve_shm_path() -> PathBuf {
    if let Ok(path) = std::env::var("DINGDA_SIDECAR_SHM") {
        return PathBuf::from(path);
    }
    std::env::temp_dir().join(format!("dingda-sidecar-{}.shm", std::process::id()))
}

fn append_sidecar_args(cmd: &mut Command, config: &SidecarConfig) {
    let ipc = config.ipc_endpoint.display();
    cmd.arg("--ipc").arg(&ipc);
}

fn build_spawn_command(config: &SidecarConfig) -> Result<Command, SidecarLifecycleError> {
    if let Some(bundled) = config.bundled_executable.as_ref() {
        if bundled.is_file() {
            let mut cmd = Command::new(bundled);
            append_sidecar_args(&mut cmd, config);
            info!(executable = %bundled.display(), "启动内置侧车");
            return Ok(configure_stdio(cmd));
        }
        warn!(
            executable = %bundled.display(),
            "内置侧车可执行文件缺失，回退到开发启动器"
        );
    }

    let sidecar_dir = path_to_str(&config.sidecar_dir);

    if config.use_uv && command_available("uv") {
        let mut cmd = Command::new("uv");
        cmd.arg("run")
            .arg("--directory")
            .arg(&sidecar_dir)
            .arg("python")
            .arg("-m")
            .arg("application.sidecar.main");
        append_sidecar_args(&mut cmd, config);
        return Ok(configure_stdio(cmd));
    }

    if config.use_uv {
        warn!("PATH 中未找到 uv，回退到 python 可执行文件");
    }

    for candidate in spawn_python_candidates(config) {
        if !command_available(&candidate) {
            continue;
        }

        let mut cmd = Command::new(&candidate);
        cmd.current_dir(&config.sidecar_dir)
            .arg("-m")
            .arg("application.sidecar.main");
        append_sidecar_args(&mut cmd, config);
        info!(executable = %candidate, "使用 python 启动侧车");
        return Ok(configure_stdio(cmd));
    }

    Err(SidecarLifecycleError::SpawnFailed(
        "PATH 中未找到 Python 运行时（请安装 uv，或确保 python/py 可用；也可设置 DINGDA_PYTHON）"
            .into(),
    ))
}

fn spawn_python_candidates(config: &SidecarConfig) -> Vec<String> {
    let mut candidates = vec![config.python_executable.clone()];
    for fallback in ["python", "python3", "py"] {
        if !candidates.iter().any(|value| value == fallback) {
            candidates.push(fallback.to_string());
        }
    }
    candidates
}

fn configure_stdio(mut command: Command) -> Command {
    command
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());
    // 透传插件目录与 Camoufox 路径（桌面端在 setup / 安装后写入进程环境）。
    if let Ok(plugins) = std::env::var("DINGDA_PLUGINS_DIR") {
        command.env("DINGDA_PLUGINS_DIR", plugins);
    }
    if let Ok(exe) = std::env::var("DINGDA_CAMOUFOX_EXE") {
        if !exe.trim().is_empty() {
            command.env("DINGDA_CAMOUFOX_EXE", exe);
        }
    }
    command
}

fn resolve_bundled_executable() -> Option<PathBuf> {
    if let Ok(path) = std::env::var("DINGDA_SIDECAR_BIN") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Some(path);
        }
    }

    if cfg!(debug_assertions) {
        return None;
    }

    let candidate = bundled_executable_candidate();
    if candidate.is_file() {
        Some(candidate)
    } else {
        None
    }
}

fn bundled_executable_candidate() -> PathBuf {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
        .unwrap_or_default();
    exe_dir.join(bundled_sidecar_filename())
}

pub fn bundled_sidecar_filename() -> String {
    let base = format!("sidecar-{}", env!("DINGDA_TARGET_TRIPLE"));
    if cfg!(target_os = "windows") {
        format!("{base}.exe")
    } else {
        base
    }
}

fn command_available(program: &str) -> bool {
    #[cfg(windows)]
    {
        std::process::Command::new("where")
            .arg(program)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }

    #[cfg(not(windows))]
    {
        std::process::Command::new("sh")
            .arg("-c")
            .arg(format!("command -v {program}"))
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }
}

fn path_to_str(path: &Path) -> String {
    path.to_string_lossy().into_owned()
}

async fn pipe_logs<R>(reader: R, stream: &'static str)
where
    R: tokio::io::AsyncRead + Unpin + Send + 'static,
{
    let mut lines = BufReader::new(reader).lines();
    while let Ok(Some(line)) = lines.next_line().await {
        events::emit_line(stream, &line);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::infrastructure::event::{EventError, EventHandler, InMemoryEventBus};
    use std::sync::{Arc, Mutex};

    type Records = Arc<Mutex<Vec<(String, Vec<u8>)>>>;

    struct RecordingHandler(Records);

    impl EventHandler for RecordingHandler {
        fn handle(&self, topic: &str, payload: &[u8]) -> Result<(), EventError> {
            self.0
                .lock()
                .map_err(|error| EventError::PublishFailed(error.to_string()))?
                .push((topic.to_string(), payload.to_vec()));
            Ok(())
        }
    }

    #[test]
    fn bundled_sidecar_filename_matches_target_triple() {
        let filename = bundled_sidecar_filename();
        assert!(filename.starts_with("sidecar-"));
        if cfg!(target_os = "windows") {
            assert!(filename.ends_with(".exe"));
        } else {
            assert!(!filename.ends_with(".exe"));
        }
    }

    #[test]
    fn publish_error_emits_runtime_error_event() {
        let bus = Arc::new(InMemoryEventBus::new());
        let config = SidecarConfig {
            port: 0,
            ipc_endpoint: IpcEndpoint::from_path(
                std::env::temp_dir().join("dingda-sidecar-test.ipc"),
            ),
            shm_path: std::env::temp_dir().join("dingda-sidecar-test.shm"),
            sidecar_dir: PathBuf::from("."),
            use_uv: false,
            python_executable: "python".to_string(),
            startup_timeout: Duration::from_secs(1),
            max_restart_attempts: 3,
            bundled_executable: None,
        };
        let lifecycle = SidecarLifecycle::new(config, bus.clone() as Arc<dyn EventBus>);
        let records: Records = Arc::new(Mutex::new(Vec::new()));
        bus.subscribe(
            RUNTIME_ERROR_TOPIC,
            Box::new(RecordingHandler(records.clone())),
        )
        .expect("subscribe");

        lifecycle.publish_error("network", "startup", "侧车启动失败".to_string());

        let events = records.lock().expect("lock");
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].0, RUNTIME_ERROR_TOPIC);
        let payload: RuntimeEventError = serde_json::from_slice(&events[0].1).expect("parse");
        assert_eq!(payload.kind, "network");
        assert_eq!(payload.stage.as_deref(), Some("startup"));
        assert_eq!(payload.message, "侧车启动失败");
        assert!(!payload.event_id.is_empty());
    }
}
