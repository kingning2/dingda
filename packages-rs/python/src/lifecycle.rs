//! 拉起 / 停止 Python Server（bundled uv + 国内镜像；dev 回退系统 uv）。

use std::collections::HashSet;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use common::logging::{self, Scope};
use common::paths::resolve_server_dir;
use reqwest::Client;
use tauri::{AppHandle, Emitter};
use thiserror::Error;
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

const DEFAULT_HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 8787;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);
/// 单次 `/health` 请求超时。
///
/// 端口被别的进程占住但不回 HTTP 时，不设超时会让 `wait_until_healthy` 卡在
/// 一次 `send()` 上，连 `startup_timeout` 兜底都进不去。
const HEALTH_TIMEOUT: Duration = Duration::from_secs(3);
/// Python 入口模块：仓库根跑 `python -m api`（`packages-py/api/src/api/__main__.py`）。
const SERVER_MODULE: &str = "api";

#[derive(Debug, Error)]
pub enum PythonLifecycleError {
    #[error("server 目录不存在: {0}")]
    ServerDirNotFound(String),
    #[error("启动 Python 失败: {0}")]
    SpawnFailed(String),
    #[error("Python 启动超时（{0:?}）")]
    StartupTimeout(Duration),
    #[error("停止 Python 失败: {0}")]
    StopFailed(String),
}

#[derive(Debug, Clone)]
pub struct PythonConfig {
    pub host: String,
    pub port: u16,
    pub server_dir: PathBuf,
    pub use_uv: bool,
    pub uv_bin: PathBuf,
    pub extra_env: Vec<(String, String)>,
    pub startup_timeout: Duration,
}

impl PythonConfig {
    pub fn from_env() -> Self {
        let port = std::env::var("DINGDA_PORT")
            .ok()
            .and_then(|value| value.parse().ok())
            .unwrap_or(DEFAULT_PORT);
        let host = std::env::var("DINGDA_HOST").unwrap_or_else(|_| DEFAULT_HOST.into());

        Self {
            host,
            port,
            server_dir: resolve_server_dir(),
            use_uv: std::env::var("DINGDA_USE_UV")
                .map(|value| value != "0")
                .unwrap_or(true),
            uv_bin: PathBuf::from(if cfg!(windows) { "uv.exe" } else { "uv" }),
            extra_env: Vec::new(),
            startup_timeout: STARTUP_TIMEOUT,
        }
    }

    pub fn api_base_url(&self) -> String {
        format!("http://{}:{}", self.host, self.port)
    }
}

/// 事件出口插座：把「往前端发事件」从 Tauri `AppHandle` 上摘下来。
///
/// 生产侧是 `AppHandle`，测试侧换成记录器，就能在 `cargo test` 里断言
/// `server-starting` / `server-ready` / `server-error` 的序列，不必起 WebView。
pub trait EventSink: Send + Sync {
    /// 发一个事件，`payload` 已是待序列化的字符串。
    fn emit_event(&self, event: &str, payload: String);
}

impl EventSink for AppHandle {
    fn emit_event(&self, event: &str, payload: String) {
        let _ = self.emit(event, payload);
    }
}

pub struct PythonLifecycle {
    config: PythonConfig,
    /// 可在启动前追加（Camoufox 解压在后台完成后注入）。
    extra_env: Mutex<Vec<(String, String)>>,
    client: Client,
    child: Mutex<Option<Child>>,
    ready: AtomicBool,
}

impl PythonLifecycle {
    pub fn new(mut config: PythonConfig) -> Self {
        let client = Client::builder()
            .timeout(HEALTH_TIMEOUT)
            .build()
            .expect("reqwest client");
        let extra_env = Mutex::new(std::mem::take(&mut config.extra_env));
        Self {
            config,
            extra_env,
            client,
            child: Mutex::new(None),
            ready: AtomicBool::new(false),
        }
    }

    /// 追加子进程环境变量（例如后台解压完成后的 `DINGDA_CAMOUFOX_EXE`）。
    pub async fn push_extra_env(&self, key: String, value: String) {
        self.extra_env.lock().await.push((key, value));
    }

    pub fn api_base_url(&self) -> String {
        self.config.api_base_url()
    }

    pub fn is_ready(&self) -> bool {
        self.ready.load(Ordering::Relaxed)
    }

    /// 后台启动 Server：sync → spawn → 探活 → emit ready/error。
    ///
    /// 每个终局都发且只发一个终态事件（`server-ready` 或 `server-error`），
    /// 前端据此离开启动屏；spawn 失败也要发，否则前端会永远停在 warming。
    pub async fn start_background(&self, events: &dyn EventSink) -> Result<(), PythonLifecycleError> {
        self.ready.store(false, Ordering::Relaxed);
        logging::log(
            Scope::Shell,
            "python server starting",
            Some(self.api_base_url().as_str()),
        );

        if self.health_check().await.unwrap_or(false) {
            logging::log(
                Scope::Shell,
                "stopping existing server on",
                Some(self.api_base_url().as_str()),
            );
            self.stop().await?;
        }

        if let Err(error) = self.spawn().await {
            logging::log(
                Scope::Shell,
                "python server spawn failed",
                Some(&error.to_string()),
            );
            events.emit_event("server-error", error.to_string());
            return Err(error);
        }

        let api_base_url = self.api_base_url();
        events.emit_event("server-starting", api_base_url.clone());

        match self.wait_until_healthy().await {
            Ok(()) => {
                self.ready.store(true, Ordering::Relaxed);
                events.emit_event("server-ready", api_base_url);
                Ok(())
            }
            Err(error) => {
                events.emit_event("server-error", error.to_string());
                Err(error)
            }
        }
    }

    pub async fn stop(&self) -> Result<(), PythonLifecycleError> {
        self.ready.store(false, Ordering::Relaxed);
        let mut guard = self.child.lock().await;
        if let Some(mut child) = guard.take() {
            kill_child_tree(&mut child).await?;
            logging::log(Scope::Shell, "python server stopped", None);
            return Ok(());
        }
        drop(guard);

        if kill_listeners_on_port(self.config.port) {
            logging::log(
                Scope::Shell,
                "python server stopped",
                Some(format!("port {}", self.config.port).as_str()),
            );
        }
        Ok(())
    }

    async fn spawn(&self) -> Result<(), PythonLifecycleError> {
        if !self.config.server_dir.is_dir() {
            return Err(PythonLifecycleError::ServerDirNotFound(
                self.config.server_dir.display().to_string(),
            ));
        }

        let host = self.config.host.clone();
        let port = self.config.port.to_string();
        let uv = self.config.uv_bin.clone();

        let extra_env = self.extra_env.lock().await.clone();

        if self.config.use_uv {
            let mut sync = Command::new(&uv);
            sync.args(["sync", "--frozen"])
                .current_dir(&self.config.server_dir)
                // stdin 不给：Server 是后台进程，继承壳的 stdin 会在父进程交互时卡住
                .stdin(Stdio::null())
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .env_remove("VIRTUAL_ENV");
            apply_extra_env(&mut sync, &extra_env);
            #[cfg(windows)]
            {
                const CREATE_NO_WINDOW: u32 = 0x0800_0000;
                sync.creation_flags(CREATE_NO_WINDOW);
            }
            match sync.status().await {
                Ok(status) if status.success() => {
                    logging::log(Scope::Shell, "python deps synced (uv sync --frozen)", None);
                }
                Ok(status) => {
                    logging::log(
                        Scope::Shell,
                        "python deps sync non-zero",
                        Some(&format!("code={}", status.code().unwrap_or(-1))),
                    );
                }
                Err(error) => {
                    logging::log(
                        Scope::Shell,
                        "python deps sync skipped",
                        Some(&error.to_string()),
                    );
                }
            }
        }

        let mut command = if self.config.use_uv {
            let mut cmd = Command::new(&uv);
            cmd.args([
                "run", "python", "-m", SERVER_MODULE, "--host", &host, "--port", &port,
            ]);
            cmd
        } else if let Some(python) = extra_env
            .iter()
            .find(|(k, _)| k == "DINGDA_PYTHON")
            .map(|(_, v)| v.clone())
        {
            let mut cmd = Command::new(python);
            cmd.args(["-m", SERVER_MODULE, "--host", &host, "--port", &port]);
            cmd
        } else {
            let mut cmd = Command::new("python");
            cmd.args(["-m", SERVER_MODULE, "--host", &host, "--port", &port]);
            cmd
        };

        command
            .current_dir(&self.config.server_dir)
            .stdin(Stdio::null())
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .kill_on_drop(true)
            .env_remove("VIRTUAL_ENV")
            .env("PYTHONUNBUFFERED", "1")
            .env("FORCE_COLOR", "1");
        apply_extra_env(&mut command, &extra_env);

        #[cfg(windows)]
        {
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }

        let child = command
            .spawn()
            .map_err(|error| PythonLifecycleError::SpawnFailed(error.to_string()))?;

        logging::log(
            Scope::Shell,
            "python server spawned at",
            Some(self.api_base_url().as_str()),
        );
        let server_dir = self.config.server_dir.display().to_string();
        logging::log(Scope::Shell, "python server dir", Some(server_dir.as_str()));
        let uv_disp = uv.display().to_string();
        logging::log(Scope::Shell, "python uv bin", Some(uv_disp.as_str()));
        *self.child.lock().await = Some(child);
        Ok(())
    }

    async fn wait_until_healthy(&self) -> Result<(), PythonLifecycleError> {
        let deadline = Instant::now() + self.config.startup_timeout;
        while Instant::now() < deadline {
            if self.health_check().await.unwrap_or(false) {
                logging::log(Scope::Shell, "python server ready", None);
                return Ok(());
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }
        self.stop().await.ok();
        Err(PythonLifecycleError::StartupTimeout(
            self.config.startup_timeout,
        ))
    }

    async fn health_check(&self) -> Result<bool, reqwest::Error> {
        let url = format!("{}/health", self.api_base_url());
        let response = self.client.get(url).send().await?;
        Ok(response.status().is_success())
    }
}

fn apply_extra_env(cmd: &mut Command, extra: &[(String, String)]) {
    for (key, value) in extra {
        cmd.env(key, value);
    }
}

async fn kill_child_tree(child: &mut Child) -> Result<(), PythonLifecycleError> {
    #[cfg(windows)]
    {
        if let Some(pid) = child.id() {
            kill_process_tree(pid);
            let _ = child.wait().await;
            return Ok(());
        }
    }

    if let Err(error) = child.start_kill() {
        return Err(PythonLifecycleError::StopFailed(error.to_string()));
    }
    if let Err(error) = child.wait().await {
        return Err(PythonLifecycleError::StopFailed(error.to_string()));
    }
    Ok(())
}

#[cfg(windows)]
fn kill_process_tree(pid: u32) {
    use std::os::windows::process::CommandExt;
    use std::process::Command;

    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();
}

#[cfg(not(windows))]
fn kill_process_tree(pid: u32) {
    let _ = pid;
}

fn kill_listeners_on_port(port: u16) -> bool {
    let pids = listeners_on_port(port);
    if pids.is_empty() {
        return false;
    }

    for pid in pids {
        kill_process_tree(pid);
    }
    true
}

fn listeners_on_port(port: u16) -> HashSet<u32> {
    #[cfg(windows)]
    {
        use std::process::Command;

        let output = match Command::new("netstat").args(["-ano"]).output() {
            Ok(output) => output,
            Err(_) => return HashSet::new(),
        };

        parse_netstat_listeners(&String::from_utf8_lossy(&output.stdout), port)
    }

    #[cfg(not(windows))]
    {
        let _ = port;
        HashSet::new()
    }
}

/// 从 `netstat -ano` 输出里挑出在 `port` 上 LISTENING 的 PID。
///
/// 按第 2 列本地地址的端口号做**全等**比较：子串匹配会让 `80` 命中 `8080`，
/// 而 `kill_listeners_on_port` 拿到的 PID 是直接 `taskkill /F` 的，会误杀无关进程。
#[cfg(windows)]
fn parse_netstat_listeners(text: &str, port: u16) -> HashSet<u32> {
    let mut pids = HashSet::new();

    for line in text.lines() {
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.len() < 5 || fields[3] != "LISTENING" {
            continue;
        }
        let listening_port = fields[1]
            .rsplit(':')
            .next()
            .and_then(|value| value.parse::<u16>().ok());
        if listening_port != Some(port) {
            continue;
        }
        if let Ok(pid) = fields[4].parse::<u32>() {
            if pid > 0 {
                pids.insert(pid);
            }
        }
    }

    pids
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex as StdMutex;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    /// 事件记录器：把 `start_background` 的状态机变成可断言的事件序列。
    struct RecordingSink {
        events: StdMutex<Vec<(String, String)>>,
    }

    impl RecordingSink {
        fn new() -> Self {
            Self {
                events: StdMutex::new(Vec::new()),
            }
        }

        fn names(&self) -> Vec<String> {
            self.events
                .lock()
                .unwrap()
                .iter()
                .map(|(name, _)| name.clone())
                .collect()
        }
    }

    impl EventSink for RecordingSink {
        fn emit_event(&self, event: &str, payload: String) {
            self.events
                .lock()
                .unwrap()
                .push((event.to_string(), payload));
        }
    }

    /// 借内核分配的空闲端口：不碰本机的 8787（dev）和 8799（E2E）。
    async fn free_port() -> u16 {
        TcpListener::bind("127.0.0.1:0")
            .await
            .unwrap()
            .local_addr()
            .unwrap()
            .port()
    }

    fn test_config(port: u16) -> PythonConfig {
        PythonConfig {
            host: "127.0.0.1".into(),
            port,
            server_dir: std::env::temp_dir(),
            use_uv: false,
            uv_bin: PathBuf::from("uv"),
            extra_env: Vec::new(),
            startup_timeout: Duration::from_millis(600),
        }
    }

    /// 假 `/health` 服务：`reply` 为 `None` 时接受连接后不回，模拟端口被占死。
    async fn spawn_fake_health(reply: Option<&'static str>) -> u16 {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        tokio::spawn(async move {
            while let Ok((mut socket, _)) = listener.accept().await {
                let mut buffer = [0u8; 1024];
                let _ = socket.read(&mut buffer).await;
                match reply {
                    Some(body) => {
                        let response = format!(
                            "HTTP/1.1 200 OK\r\nContent-Length: {}\r\n\r\n{}",
                            body.len(),
                            body
                        );
                        let _ = socket.write_all(response.as_bytes()).await;
                    }
                    None => tokio::time::sleep(Duration::from_secs(30)).await,
                }
            }
        });
        port
    }

    #[test]
    fn resolves_server_dir_to_repo_workspace_root() {
        let config = PythonConfig::from_env();
        assert_eq!(config.server_dir, resolve_server_dir());
        assert!(config.server_dir.join("pyproject.toml").is_file());
        assert!(config.server_dir.join("packages-py").is_dir());
    }

    #[tokio::test]
    async fn health_check_returns_true_on_200() {
        let port = spawn_fake_health(Some("ok")).await;
        let lifecycle = PythonLifecycle::new(test_config(port));

        assert!(lifecycle.health_check().await.unwrap_or(false));
    }

    #[tokio::test]
    async fn health_check_gives_up_when_server_never_replies() {
        let port = spawn_fake_health(None).await;
        let lifecycle = PythonLifecycle::new(test_config(port));

        let started = Instant::now();
        assert!(!lifecycle.health_check().await.unwrap_or(false));
        assert!(
            started.elapsed() < Duration::from_secs(10),
            "/health 必须有请求超时，否则 wait_until_healthy 会永久卡住"
        );
    }

    #[tokio::test]
    async fn spawn_failure_still_emits_server_error() {
        let mut config = test_config(free_port().await);
        config.server_dir = PathBuf::from("D:/dingda-no-such-server-dir");
        let lifecycle = PythonLifecycle::new(config);
        let sink = RecordingSink::new();

        let error = lifecycle.start_background(&sink).await.unwrap_err();

        assert!(matches!(
            error,
            PythonLifecycleError::ServerDirNotFound(_)
        ));
        // spawn 就失败时不发 server-starting，但必须发 server-error，
        // 否则前端停在 warming 没有任何出口
        assert_eq!(sink.names(), vec!["server-error".to_string()]);
        assert!(!lifecycle.is_ready());
    }

    #[tokio::test]
    async fn startup_timeout_leaves_lifecycle_not_ready() {
        let lifecycle = PythonLifecycle::new(test_config(free_port().await));

        let error = lifecycle.wait_until_healthy().await.unwrap_err();

        assert!(matches!(error, PythonLifecycleError::StartupTimeout(_)));
        assert!(!lifecycle.is_ready());
    }

    #[cfg(windows)]
    #[test]
    fn parses_netstat_listeners_by_exact_port() {
        let output = [
            "  Proto  Local Address          Foreign Address        State           PID",
            "  TCP    0.0.0.0:80             0.0.0.0:0              LISTENING       111",
            "  TCP    127.0.0.1:8080         0.0.0.0:0              LISTENING       222",
            "  TCP    [::]:8787              [::]:0                 LISTENING       333",
            "  TCP    0.0.0.0:8787           0.0.0.0:0              LISTENING       333",
            "  TCP    10.0.0.5:8787          10.0.0.9:54321         ESTABLISHED     444",
            "  UDP    0.0.0.0:5353           *:*                                    555",
        ]
        .join("\n");

        assert_eq!(
            parse_netstat_listeners(&output, 8787),
            HashSet::from([333])
        );
        // 80 不能靠子串命中 8080 —— 命中的 PID 会被直接 taskkill
        assert_eq!(parse_netstat_listeners(&output, 80), HashSet::from([111]));
    }
}
