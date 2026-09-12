//! Runtime 公共类型：Definition 是各 CLI 插头必须填的插座。

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
pub type DiscoverModelsFn =
    for<'a> fn(&'a Path) -> Pin<Box<dyn Future<Output = Vec<RuntimeModel>> + Send + 'a>>;

/// 鉴权探针输出的解析方式。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthParse {
    /// 退出码 0 即已登录（codex `login status`）。
    ExitCode,
    /// stdout 是 JSON，取 `loggedIn` 布尔（claude `auth status`）。
    JsonLoggedIn,
    /// 输出里 `N credentials`，N>0 即已登录（opencode `auth list`）。
    CredentialCount,
}

/// 单个 Runtime 的鉴权契约：怎么探、怎么登、登完提示什么。
#[derive(Debug, Clone, Copy)]
pub struct RuntimeAuth {
    pub probe_args: &'static [&'static str],
    pub parse: AuthParse,
    /// 空切片 = 不支持由平台触发登录。
    pub login_args: &'static [&'static str],
    pub login_message: &'static str,
}

/// 可执行文件解析来源。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum ExecutableSource {
    Configured,
    /// 叮答托管目录（`~/.dingda/v2/runtimes/<id>/`）。
    Managed,
    Path,
    KnownLocation,
}

impl ExecutableSource {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Configured => "configured",
            Self::Managed => "managed",
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

/// 单个 CLI 的运行时定义（探测 / 下载 / catalog；启动参数在 Python spawn）。
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
    /// 可选：本 Runtime 的鉴权探针与登录入口（无 CLI 登录时为 `None`）。
    pub auth: Option<RuntimeAuth>,
    pub install_url: &'static str,
    pub docs_url: &'static str,
    pub external_mcp_injection: Option<&'static str>,
    pub is_default: bool,
    /// 可选：发现阶段额外校验。
    pub validate_executable: Option<fn(&Path) -> bool>,
    /// 探测可用模型列表。
    pub discover_models: DiscoverModelsFn,
    /// 可选：叮答托管一键下载规格（统一由 `defs/base` 执行）。
    pub managed_download: Option<ManagedDownloadSpec>,
}

/// 托管下载规格：各插头只填 URL 与平台资源名，下载逻辑在 `defs/base`。
#[derive(Debug, Clone, Copy)]
pub struct ManagedDownloadSpec {
    /// 如 `https://github.com/.../releases/latest/download`
    pub release_base_url: &'static str,
    /// 返回当前平台资源路径（可含 `/`，如 `win32-x64/claude.exe`；或 `*.zip` / `*.tar.gz` / 裸 `.exe`）。
    pub asset_name: fn() -> Result<&'static str, String>,
    /// 若有：先 GET `{base}/{version_file}` 取版本号，再拼 `{base}/{version}/{asset}`（Claude）。
    pub version_file: Option<&'static str>,
}

impl RuntimeDefinition {
    pub fn all_binary_names(&self) -> Vec<&str> {
        let mut names = vec![self.binary];
        names.extend(self.fallback_binaries);
        names
    }

    /// 是否能由平台触发登录（有 `auth` 且 `login_args` 非空）。
    pub fn can_login(&self) -> bool {
        self.auth.is_some_and(|auth| !auth.login_args.is_empty())
    }
}
