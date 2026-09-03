use std::collections::HashMap;
use std::future::Future;
use std::path::{Path, PathBuf};
use std::pin::Pin;

use serde::Serialize;

/// CLI 探测到的可用模型。
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeModel {
    pub id: String,
    pub label: String,
}

/// 模型发现函数（每个 Runtime 在 defs 中注册）。
pub type DiscoverModelsFn = for<'a> fn(
    &'a Path,
) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + 'a>>;

/// CLI 输出流格式 — 决定使用哪个 Parser。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StreamFormat {
    ClaudeStreamJson,
    JsonEventStream,
    CopilotStreamJson,
    QoderStreamJson,
    AcpJsonRpc,
    PiRpc,
    DshProfileJsonl,
    Plain,
}

/// 运行时能力声明（数据驱动，不含行为）。
#[derive(Debug, Clone, Copy, Default)]
pub struct RuntimeCapabilities {
    pub login_capable: bool,
    pub supports_resume: bool,
    pub supports_images: bool,
    pub prompt_via_stdin: bool,
}

/// 一次 CLI 调用的上下文（供 `build_args` 使用）。
#[derive(Debug, Clone)]
pub struct RuntimeInvocationContext {
    pub runtime_id: String,
    pub prompt: String,
    pub cwd: PathBuf,
    pub model: Option<String>,
    pub extra_allowed_dirs: Vec<PathBuf>,
}

/// 启动 CLI 进程所需的完整参数。
#[derive(Debug, Clone)]
pub struct RuntimeInvocation {
    pub runtime_id: String,
    pub executable: PathBuf,
    pub args: Vec<String>,
    pub cwd: PathBuf,
    pub env: HashMap<String, String>,
    pub prompt_via_stdin: bool,
    pub prompt: Option<String>,
}

/// 可执行文件解析来源。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum ExecutableSource {
    Configured,
    Path,
    KnownLocation,
}

impl ExecutableSource {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Configured => "configured",
            Self::Path => "path",
            Self::KnownLocation => "knownLocation",
        }
    }
}

/// 解析后的可执行文件。
#[derive(Debug, Clone)]
pub struct ResolvedExecutable {
    pub path: PathBuf,
    pub source: ExecutableSource,
}

/// 运行时探测结果。
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeDetection {
    pub available: bool,
    pub executable: Option<String>,
    pub version: Option<String>,
    pub source: Option<ExecutableSource>,
    pub authenticated: Option<bool>,
    pub error: Option<String>,
}

/// 单个 CLI 的运行时定义（数据 + 纯函数指针，无 per-agent 子类）。
#[derive(Debug, Clone, Copy)]
pub struct RuntimeDefinition {
    pub id: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    /// PATH 上探测用的主命令名。
    pub binary: &'static str,
    pub fallback_binaries: &'static [&'static str],
    /// 用户配置路径环境变量（如 `DINGDA_CODEX_PATH`）。
    pub path_env_var: &'static str,
    pub version_args: &'static [&'static str],
    pub stream_format: StreamFormat,
    pub capabilities: RuntimeCapabilities,
    pub install_url: &'static str,
    pub docs_url: &'static str,
    pub external_mcp_injection: Option<&'static str>,
    pub is_default: bool,
    /// 构建 CLI 启动参数。
    pub build_args: fn(&RuntimeInvocationContext) -> Vec<String>,
    /// 可选：发现阶段额外校验（如 DSH probe）。
    pub validate_executable: Option<fn(&Path) -> bool>,
    /// 可选：认证探测参数（如 `["login", "status"]`）。
    pub auth_probe_args: Option<&'static [&'static str]>,
    /// 探测可用模型列表。
    pub discover_models: DiscoverModelsFn,
}

impl RuntimeDefinition {
    pub fn all_binary_names(&self) -> Vec<&str> {
        let mut names = vec![self.binary];
        names.extend(self.fallback_binaries);
        names
    }
}
