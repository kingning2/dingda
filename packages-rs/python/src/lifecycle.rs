//! 拉起 / 停止 Python Server（bundled uv + 国内镜像；dev 回退系统 uv）。

use std::collections::HashSet;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use common::logging::{self, Scope};
use common::paths::resolve_server_dir;
use reqwest::Client;
use tauri::{AppHandle, Emitter};
use thiserror::Error;
use tokio::process::{Child, Command};
use tokio::sync::{watch, Mutex};

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
/// 运行期探活间隔（watchdog）。
const HEALTH_INTERVAL: Duration = Duration::from_secs(15);
/// 连续失败多少次判定崩溃：15s × 2 ≈ 30s 不可用才动手，避免误杀瞬时抖动。
const HEALTH_FAILURES_BEFORE_RESTART: u32 = 2;
/// 崩溃后最多自动重启次数，耗尽则发 `server-error` 终态并停手。
const MAX_RESTART_ATTEMPTS: u32 = 3;
/// 重启退避基数（第 n 次重试前等 backoff × 2^(n-1)：2s → 4s → 8s）。
const RESTART_BACKOFF: Duration = Duration::from_secs(2);

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
    /// 运行期探活间隔；测试收缩到毫秒级。
    pub health_interval: Duration,
    /// 重启退避基数；测试收缩到毫秒级。
    pub restart_backoff: Duration,
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
            health_interval: HEALTH_INTERVAL,
            restart_backoff: RESTART_BACKOFF,
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
    client: Client,
    child: Mutex<Option<Child>>,
    ready: AtomicBool,
    /// 退出旗标：`stop()`（用户退出）置 true，监督循环看到即收工。
    stopping: watch::Sender<bool>,
}

impl PythonLifecycle {
    pub fn new(config: PythonConfig) -> Self {
        let client = Client::builder()
            .timeout(HEALTH_TIMEOUT)
            .build()
            .expect("reqwest client");
        Self {
            config,
            client,
            child: Mutex::new(None),
            ready: AtomicBool::new(false),
            stopping: watch::channel(false).0,
        }
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
    pub async fn start_background(
        &self,
        events: &dyn EventSink,
    ) -> Result<(), PythonLifecycleError> {
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
            // 只杀进程，不置退出旗标——这属于启动准备，不是用户退出
            self.kill_all().await?;
        }

        let boot_started = Instant::now();
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

        match self.wait_until_healthy(boot_started).await {
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
        // 先置旗标再杀进程：监督循环看到旗标就收工，不会抢在退出后再拉起
        let _ = self.stopping.send(true);
        self.ready.store(false, Ordering::Relaxed);
        self.kill_all().await
    }

    /// 常驻监督：周期探活，连续失败判定崩溃后自动重启。
    ///
    /// 只在 `start_background` 成功后启动，随 `stop()`（用户退出）结束。
    /// 恢复成功重发 `server-ready`（前端状态机原样接住），重试耗尽发
    /// `server-error` 终态并停手——之后不再自愈，避免退出边缘的僵尸拉起。
    pub async fn supervise(self: Arc<Self>, events: &dyn EventSink) {
        let mut stopping = self.stopping.subscribe();
        let mut interval = tokio::time::interval(self.config.health_interval);
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
        let mut failures: u32 = 0;
        loop {
            tokio::select! {
                _ = stopping.changed() => {
                    if *stopping.borrow() {
                        break;
                    }
                }
                _ = interval.tick() => {
                    if *stopping.borrow() {
                        break;
                    }
                    if self.health_check().await.unwrap_or(false) {
                        failures = 0;
                        continue;
                    }
                    failures += 1;
                    if failures < HEALTH_FAILURES_BEFORE_RESTART {
                        logging::log(
                            Scope::Shell,
                            "python server health check failed",
                            Some(&format!("{failures}/{HEALTH_FAILURES_BEFORE_RESTART}")),
                        );
                        continue;
                    }
                    failures = 0;
                    if self.restart_with_retry(events).await.is_err() {
                        break;
                    }
                }
            }
        }
        logging::log(Scope::Shell, "python supervisor exited", None);
    }

    /// 崩溃恢复：带退避重试「杀旧 → spawn → 探活」。
    ///
    /// 成功重发 `server-ready`；重试耗尽发 `server-error` 并返回 `Err`。
    async fn restart_with_retry(&self, events: &dyn EventSink) -> Result<(), ()> {
        let url = self.api_base_url();
        events.emit_event("server-starting", url.clone());
        logging::log(
            Scope::Shell,
            "python server crashed, restarting",
            Some(url.as_str()),
        );
        let restart_started = Instant::now();
        for attempt in 1..=MAX_RESTART_ATTEMPTS {
            let stopping = self.stopping.subscribe();
            if *stopping.borrow() {
                return Ok(()); // 用户退出中，不算失败
            }
            if attempt > 1 {
                tokio::time::sleep(self.config.restart_backoff * (1u32 << (attempt - 2))).await;
            }
            self.kill_child().await;
            if let Err(error) = self.spawn().await {
                logging::log(
                    Scope::Shell,
                    "python restart spawn failed",
                    Some(&error.to_string()),
                );
                continue;
            }
            if self.wait_until_healthy(restart_started).await.is_ok() {
                self.ready.store(true, Ordering::Relaxed);
                events.emit_event("server-ready", url);
                logging::log(
                    Scope::Shell,
                    "python server recovered",
                    Some(&format!(
                        "elapsed={:.1}s",
                        restart_started.elapsed().as_secs_f32()
                    )),
                );
                return Ok(());
            }
        }
        self.ready.store(false, Ordering::Relaxed);
        let message = format!("自动重启 {MAX_RESTART_ATTEMPTS} 次仍未恢复");
        events.emit_event("server-error", message);
        Err(())
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

        if self.config.use_uv {
            let mut sync = Command::new(&uv);
            sync.args(["sync", "--frozen"])
                .current_dir(&self.config.server_dir)
                // stdin 不给：Server 是后台进程，继承壳的 stdin 会在父进程交互时卡住
                .stdin(Stdio::null())
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .env_remove("VIRTUAL_ENV");
            apply_extra_env(&mut sync, &self.config.extra_env);
            #[cfg(windows)]
            {
                const CREATE_NO_WINDOW: u32 = 0x0800_0000;
                sync.creation_flags(CREATE_NO_WINDOW);
            }
            let sync_started = Instant::now();
            match sync.status().await {
                Ok(status) if status.success() => {
                    logging::log(
                        Scope::Shell,
                        "python deps synced (uv sync --frozen)",
                        Some(&format!("elapsed={:.1}s", sync_started.elapsed().as_secs_f32())),
                    );
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
                "run",
                "python",
                "-m",
                SERVER_MODULE,
                "--host",
                &host,
                "--port",
                &port,
            ]);
            cmd
        } else if let Some(python) = self
            .config
            .extra_env
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
        apply_extra_env(&mut command, &self.config.extra_env);

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

    async fn wait_until_healthy(&self, boot_started: Instant) -> Result<(), PythonLifecycleError> {
        let deadline = Instant::now() + self.config.startup_timeout;
        while Instant::now() < deadline {
            if self.health_check().await.unwrap_or(false) {
                logging::log(
                    Scope::Shell,
                    "python server ready",
                    Some(&format!("elapsed={:.1}s", boot_started.elapsed().as_secs_f32())),
                );
                return Ok(());
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }
        // 启动超时清理：只回收子进程，不置退出旗标（退出旗标是 stop() 的专属语义）
        self.kill_child().await;
        Err(PythonLifecycleError::StartupTimeout(
            self.config.startup_timeout,
        ))
    }

    async fn health_check(&self) -> Result<bool, reqwest::Error> {
        let url = format!("{}/health", self.api_base_url());
        let response = self.client.get(url).send().await?;
        Ok(response.status().is_success())
    }

    /// 只回收自己 spawn 的子进程，不做端口兑底。
    ///
    /// 崩溃进程的端口由 OS 随进程消亡自动回收；兑底杀「监听者」在恢复路径上
    /// 反而可能误伤（例如探活指向的调试服务）。已退出的子进程只 wait 回收句
    /// 柄，不 taskkill——PID 可能已被系统复用。
    async fn kill_child(&self) {
        let mut guard = self.child.lock().await;
        if let Some(mut child) = guard.take() {
            if matches!(child.try_wait(), Ok(Some(_))) {
                let _ = child.wait().await;
            } else {
                kill_child_tree(&mut child).await.ok();
            }
        }
    }

    /// 杀子进程 + 端口兑底（子进程句柄丢失时用），仅限退出 / 启动准备路径。
    async fn kill_all(&self) -> Result<(), PythonLifecycleError> {
        let mut had_child = false;
        {
            let mut guard = self.child.lock().await;
            if let Some(mut child) = guard.take() {
                kill_child_tree(&mut child).await?;
                had_child = true;
            }
        }
        if had_child {
            logging::log(Scope::Shell, "python server stopped", None);
        } else if kill_listeners_on_port(self.config.port) {
            logging::log(
                Scope::Shell,
                "python server stopped",
                Some(format!("port {}", self.config.port).as_str()),
            );
        }
        Ok(())
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
            health_interval: Duration::from_millis(50),
            restart_backoff: Duration::from_millis(10),
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

        assert!(matches!(error, PythonLifecycleError::ServerDirNotFound(_)));
        // spawn 就失败时不发 server-starting，但必须发 server-error，
        // 否则前端停在 warming 没有任何出口
        assert_eq!(sink.names(), vec!["server-error".to_string()]);
        assert!(!lifecycle.is_ready());
    }

    #[tokio::test]
    async fn startup_timeout_leaves_lifecycle_not_ready() {
        let lifecycle = PythonLifecycle::new(test_config(free_port().await));

        let error = lifecycle
            .wait_until_healthy(Instant::now())
            .await
            .unwrap_err();

        assert!(matches!(error, PythonLifecycleError::StartupTimeout(_)));
        assert!(!lifecycle.is_ready());
    }

    /// 可开关的假 `/health`：`healthy=false` 时回 503，模拟 Server 崩溃。
    async fn spawn_switchable_health() -> (u16, Arc<AtomicBool>) {
        let healthy = Arc::new(AtomicBool::new(true));
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let flag = Arc::clone(&healthy);
        tokio::spawn(async move {
            while let Ok((mut socket, _)) = listener.accept().await {
                let mut buffer = [0u8; 1024];
                let _ = socket.read(&mut buffer).await;
                let response = if flag.load(Ordering::Relaxed) {
                    "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
                } else {
                    "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n"
                };
                let _ = socket.write_all(response.as_bytes()).await;
            }
        });
        (port, healthy)
    }

    /// 轮询等事件出现，等不到就带实际序列 panic。
    async fn wait_for_event(sink: &RecordingSink, name: &str) {
        let deadline = Instant::now() + Duration::from_secs(3);
        while Instant::now() < deadline {
            if sink.names().iter().any(|event| event == name) {
                return;
            }
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
        panic!("等不到事件 {name}，实际序列 {:?}", sink.names());
    }

    #[tokio::test]
    async fn supervisor_recovers_after_transient_outage() {
        let (port, healthy) = spawn_switchable_health().await;
        let mut config = test_config(port);
        // spawn 阶段用「秒退命令」顶位：探活靠假服务，不真拉 Python
        config.extra_env = vec![(
            "DINGDA_PYTHON".into(),
            if cfg!(windows) { "cmd" } else { "true" }.into(),
        )];
        let lifecycle = Arc::new(PythonLifecycle::new(config));
        let sink = Arc::new(RecordingSink::new());
        let task_sink = Arc::clone(&sink);
        let task = tokio::spawn(async move {
            lifecycle.supervise(task_sink.as_ref()).await;
        });

        healthy.store(false, Ordering::Relaxed);
        wait_for_event(&sink, "server-starting").await;
        healthy.store(true, Ordering::Relaxed);
        wait_for_event(&sink, "server-ready").await;

        let names = sink.names();
        assert!(
            names
                .windows(2)
                .any(|pair| pair[0] == "server-starting" && pair[1] == "server-ready"),
            "必须是 starting → ready，实际序列 {names:?}"
        );
        // 收尾不调 stop()：测试进程自己就是端口监听者，端口兑底的 netstat 会误伤
        let _ = tokio::time::timeout(Duration::from_secs(1), task).await;
    }

    #[tokio::test]
    async fn supervisor_gives_up_after_retry_exhaustion() {
        let (port, healthy) = spawn_switchable_health().await;
        let mut config = test_config(port);
        config.server_dir = PathBuf::from("D:/dingda-no-such-server-dir"); // spawn 必败
        let lifecycle = Arc::new(PythonLifecycle::new(config));
        let sink = Arc::new(RecordingSink::new());
        let task_sink = Arc::clone(&sink);
        let task = tokio::spawn(async move {
            lifecycle.supervise(task_sink.as_ref()).await;
        });

        healthy.store(false, Ordering::Relaxed);
        let _ = tokio::time::timeout(Duration::from_secs(3), task)
            .await
            .expect("重试耗尽后监督任务必须自己结束");

        assert_eq!(
            sink.names(),
            vec!["server-starting".to_string(), "server-error".to_string()]
        );
    }

    #[tokio::test]
    async fn stop_cancels_supervision() {
        // 端口上没有任何监听者：stop() 的端口兑底扫 netstat 不会误伤测试进程
        let lifecycle = Arc::new(PythonLifecycle::new(test_config(free_port().await)));
        let task_lifecycle = Arc::clone(&lifecycle);
        let sink = Arc::new(RecordingSink::new());
        let task_sink = Arc::clone(&sink);
        let task = tokio::spawn(async move {
            task_lifecycle.supervise(task_sink.as_ref()).await;
        });
        // 先探活失败一两次（低于崩溃阈值），确保监督循环真的在转
        tokio::time::sleep(Duration::from_millis(120)).await;

        lifecycle.stop().await.ok();

        let _ = tokio::time::timeout(Duration::from_secs(2), task)
            .await
            .expect("stop() 后监督循环必须退出");
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

        assert_eq!(parse_netstat_listeners(&output, 8787), HashSet::from([333]));
        // 80 不能靠子串命中 8080 —— 命中的 PID 会被直接 taskkill
        assert_eq!(parse_netstat_listeners(&output, 80), HashSet::from([111]));
    }
}
