//! Spawn and stop the v2 FastAPI server (`uv run python -m src`).

use std::collections::HashSet;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use chrono::{FixedOffset, Utc};

use crate::paths::resolve_server_dir;
use reqwest::Client;
use thiserror::Error;
use tauri::{AppHandle, Emitter};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;

const DEFAULT_HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 8787;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);

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
            startup_timeout: STARTUP_TIMEOUT,
        }
    }

    pub fn api_base_url(&self) -> String {
        format!("http://{}:{}", self.host, self.port)
    }
}

pub struct PythonLifecycle {
    config: PythonConfig,
    child: Mutex<Option<Child>>,
    ready: AtomicBool,
}

impl PythonLifecycle {
    pub fn new(config: PythonConfig) -> Self {
        Self {
            config,
            child: Mutex::new(None),
            ready: AtomicBool::new(false),
        }
    }

    pub fn api_base_url(&self) -> String {
        self.config.api_base_url()
    }

    pub fn is_ready(&self) -> bool {
        self.ready.load(Ordering::Relaxed)
    }

    /// 在后台拉起 Python 并探活，不阻塞窗口显示。
    pub async fn start_background(&self, app: AppHandle) -> Result<(), PythonLifecycleError> {
        self.ready.store(false, Ordering::Relaxed);

        if self.health_check().await.unwrap_or(false) {
            log_shell(
                "stopping existing server on",
                Some(self.api_base_url().as_str()),
            );
            self.stop().await?;
        }

        self.spawn().await?;
        let api_base_url = self.api_base_url();
        let _ = app.emit("server-starting", api_base_url.clone());

        match self.wait_until_healthy().await {
            Ok(()) => {
                self.ready.store(true, Ordering::Relaxed);
                let _ = app.emit("server-ready", api_base_url);
                Ok(())
            }
            Err(error) => {
                let _ = app.emit("server-error", error.to_string());
                Err(error)
            }
        }
    }

    // #[allow(dead_code)]
    // pub async fn start(&self) -> Result<(), PythonLifecycleError> {
    //     if self.health_check().await.unwrap_or(false) {
    //         log_shell(
    //             "stopping existing server on",
    //             Some(self.api_base_url().as_str()),
    //         );
    //         self.stop().await?;
    //     }

    //     self.spawn().await?;
    //     self.wait_until_healthy().await?;
    //     self.ready.store(true, Ordering::Relaxed);
    //     Ok(())
    // }

    pub async fn stop(&self) -> Result<(), PythonLifecycleError> {
        self.ready.store(false, Ordering::Relaxed);
        let mut guard = self.child.lock().await;
        if let Some(mut child) = guard.take() {
            kill_child_tree(&mut child).await?;
            log_shell("python server stopped", None);
            return Ok(());
        }
        drop(guard);

        if kill_listeners_on_port(self.config.port) {
            log_shell(
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
        if self.config.use_uv {
            // 安装/首次启动时把 Python 依赖拉齐
            let mut sync = Command::new("uv");
            sync.args(["sync", "--frozen"])
                .current_dir(&self.config.server_dir)
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .env_remove("VIRTUAL_ENV");
            #[cfg(windows)]
            {
                const CREATE_NO_WINDOW: u32 = 0x0800_0000;
                sync.creation_flags(CREATE_NO_WINDOW);
            }
            match sync.status().await {
                Ok(status) if status.success() => {
                    log_shell("python deps synced (uv sync --frozen)", None);
                }
                Ok(status) => {
                    log_shell(
                        "python deps sync non-zero",
                        Some(&format!("code={}", status.code().unwrap_or(-1))),
                    );
                }
                Err(error) => {
                    log_shell("python deps sync skipped", Some(&error.to_string()));
                }
            }
        }
        let mut command = if self.config.use_uv {
            let mut cmd = Command::new("uv");
            cmd.args([
                "run",
                "python",
                "-m",
                "src",
                "--host",
                &host,
                "--port",
                &port,
            ]);
            cmd
        } else {
            let mut cmd = Command::new("python");
            cmd.args(["-m", "src", "--host", &host, "--port", &port]);
            cmd
        };

        command
            .current_dir(&self.config.server_dir)
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .kill_on_drop(true)
            .env_remove("VIRTUAL_ENV")
            .env("PYTHONUNBUFFERED", "1")
            .env("FORCE_COLOR", "1");

        #[cfg(windows)]
        {
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }

        let child = command
            .spawn()
            .map_err(|error| PythonLifecycleError::SpawnFailed(error.to_string()))?;

        log_shell("python server spawned at", Some(self.api_base_url().as_str()));
        let server_dir = self.config.server_dir.display().to_string();
        log_shell("python server dir", Some(server_dir.as_str()));
        *self.child.lock().await = Some(child);
        Ok(())
    }

    async fn wait_until_healthy(&self) -> Result<(), PythonLifecycleError> {
        let deadline = Instant::now() + self.config.startup_timeout;
        while Instant::now() < deadline {
            if self.health_check().await.unwrap_or(false) {
                log_shell("python server ready", None);
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
        let response = Client::new().get(url).send().await?;
        Ok(response.status().is_success())
    }
}

fn log_shell(message: &str, detail: Option<&str>) {
    let prefix = "\x1b[1;36m[shell]\x1b[0m";
    let timestamp = beijing_timestamp();
    match detail {
        Some(detail) => eprintln!("{prefix} {timestamp} {message} {detail}"),
        None => eprintln!("{prefix} {timestamp} {message}"),
    }
}

fn beijing_timestamp() -> String {
    let offset = FixedOffset::east_opt(8 * 3600).expect("beijing offset");
    Utc::now()
        .with_timezone(&offset)
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
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

        let text = String::from_utf8_lossy(&output.stdout);
        let needle = format!(":{port}");
        let mut pids = HashSet::new();

        for line in text.lines() {
            if !line.contains("LISTENING") || !line.contains(&needle) {
                continue;
            }
            if let Some(pid) = line.split_whitespace().last() {
                if let Ok(pid) = pid.parse::<u32>() {
                    if pid > 0 {
                        pids.insert(pid);
                    }
                }
            }
        }

        pids
    }

    #[cfg(not(windows))]
    {
        let _ = port;
        HashSet::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::paths::resolve_server_dir;

    #[test]
    fn resolves_server_dir_relative_to_manifest() {
        let config = PythonConfig::from_env();
        assert!(config.server_dir.ends_with("server"));
        assert_eq!(config.server_dir, resolve_server_dir());
    }
}
