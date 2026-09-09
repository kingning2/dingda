use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use super::types::{ExecutableSource, ResolvedExecutable, RuntimeDefinition};

const SHELL_RESOLVE_TTL: Duration = Duration::from_secs(30 * 60);
static SHELL_CACHE: Mutex<Option<ShellCache>> = Mutex::new(None);

#[derive(Debug, Clone)]
struct ShellCache {
    key: String,
    resolved_at: Instant,
    paths: HashMap<String, PathBuf>,
}

/// 统一可执行文件解析入口。
/// 顺序：用户配置 → 叮答托管目录 → 动态 PATH → 已知安装目录。
pub fn resolve_executable(definition: &RuntimeDefinition) -> Option<ResolvedExecutable> {
    if let Some(resolved) = resolve_configured(definition) {
        return Some(resolved);
    }

    if let Some(resolved) = definition.resolve_managed() {
        if validate_executable(definition, &resolved.path) {
            return Some(resolved);
        }
    }

    for name in definition.all_binary_names() {
        if let Some(resolved) = resolve_on_dynamic_path(name) {
            if validate_executable(definition, &resolved.path) {
                return Some(resolved);
            }
        }
    }

    for name in definition.all_binary_names() {
        if let Some(path) = resolve_known_location(definition, name) {
            if validate_executable(definition, &path) {
                return Some(ResolvedExecutable {
                    path,
                    source: ExecutableSource::KnownLocation,
                });
            }
        }
    }

    // Codex macOS desktop bundle 特例
    if definition.id == "codex" {
        if let Some(path) = codex_desktop_bundle_path() {
            return Some(ResolvedExecutable {
                path,
                source: ExecutableSource::KnownLocation,
            });
        }
    }

    None
}

fn resolve_configured(definition: &RuntimeDefinition) -> Option<ResolvedExecutable> {
    let configured = std::env::var(definition.path_env_var)
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())?;

    let path = PathBuf::from(&configured);
    let path_str = path.to_string_lossy();
    if path_str.contains('/') || path_str.contains('\\') {
        return is_executable_file(&path).then_some(ResolvedExecutable {
            path: canonicalize_path(&path),
            source: ExecutableSource::Configured,
        });
    }

    resolve_on_dynamic_path(&configured).map(|mut resolved| {
        resolved.source = ExecutableSource::Configured;
        resolved
    })
}

fn resolve_on_dynamic_path(cmd: &str) -> Option<ResolvedExecutable> {
    if cmd.contains('/') || cmd.contains('\\') {
        let path = PathBuf::from(cmd);
        return is_executable_file(&path).then_some(ResolvedExecutable {
            path: canonicalize_path(&path),
            source: ExecutableSource::Path,
        });
    }

    if let Some(path) = resolve_on_path(cmd, std::env::var_os("PATH").as_deref()) {
        return Some(ResolvedExecutable {
            path,
            source: ExecutableSource::Path,
        });
    }

    for path_var in dynamic_path_vars() {
        if let Some(path) = resolve_on_path(cmd, Some(path_var.as_os_str())) {
            return Some(ResolvedExecutable {
                path,
                source: ExecutableSource::Path,
            });
        }
    }

    if let Some(path) = cached_shell_resolved(cmd) {
        return Some(ResolvedExecutable {
            path,
            source: ExecutableSource::Path,
        });
    }

    None
}

/// 合并进程 PATH 与系统最新 PATH（Windows 注册表 / Unix login shell）。
fn dynamic_path_vars() -> Vec<std::ffi::OsString> {
    let mut vars = Vec::new();
    #[cfg(windows)]
    if let Some(fresh) = windows_fresh_path_var() {
        vars.push(fresh);
    }
    vars
}

fn resolve_on_path(cmd: &str, path_var: Option<&std::ffi::OsStr>) -> Option<PathBuf> {
    let path_var = path_var?;
    let pathext = if cfg!(windows) {
        std::env::var("PATHEXT").unwrap_or_else(|_| ".EXE;.CMD;.BAT".to_string())
    } else {
        String::new()
    };
    let extensions: Vec<&str> = if cfg!(windows) {
        pathext
            .split(';')
            .map(str::trim)
            .filter(|ext| !ext.is_empty())
            .collect()
    } else {
        vec![""]
    };

    for dir in std::env::split_paths(path_var) {
        for ext in &extensions {
            let candidate = if ext.is_empty() {
                dir.join(cmd)
            } else {
                let stem = cmd.trim_end_matches(ext);
                dir.join(format!("{stem}{ext}"))
            };
            if is_executable_file(&candidate) {
                return Some(canonicalize_path(&candidate));
            }
        }
    }
    None
}

/// Windows：从注册表读取 Machine + User PATH，不依赖 DingDa 启动时的进程环境。
#[cfg(windows)]
fn windows_fresh_path_var() -> Option<std::ffi::OsString> {
    use std::ffi::OsString;

    let machine = read_registry_path("HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment", "Path");
    let user = read_registry_path("HKCU\\Environment", "Path");

    let combined = match (machine, user) {
        (Some(m), Some(u)) => format!("{m};{u}"),
        (Some(m), None) => m,
        (None, Some(u)) => u,
        (None, None) => {
            return windows_fresh_path_via_powershell();
        }
    };

    if combined.trim().is_empty() {
        return windows_fresh_path_via_powershell();
    }

    Some(OsString::from(combined))
}

#[cfg(windows)]
fn read_registry_path(hive_key: &str, value_name: &str) -> Option<String> {
    let output = std::process::Command::new("reg")
        .args(["query", hive_key, "/v", value_name])
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let text = String::from_utf8_lossy(&output.stdout);
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with("HKEY_") {
            continue;
        }
        if let Some((_, value)) = trimmed.split_once("REG_") {
            let value = value
                .split_once(' ')
                .map(|(_, rest)| rest.trim())
                .unwrap_or(value.trim());
            if !value.is_empty() {
                return Some(value.to_string());
            }
        }
    }
    None
}

#[cfg(windows)]
fn windows_fresh_path_via_powershell() -> Option<std::ffi::OsString> {
    use std::ffi::OsString;

    let output = std::process::Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')",
        ])
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output()
        .ok()?;

    if !output.status.success() && output.stdout.is_empty() {
        return None;
    }

    let path = String::from_utf8_lossy(&output.stdout)
        .trim()
        .trim_end_matches(';')
        .to_string();
    if path.is_empty() {
        return None;
    }
    Some(OsString::from(path))
}

#[cfg(not(windows))]
fn windows_fresh_path_var() -> Option<std::ffi::OsString> {
    None
}

pub fn known_locations() -> Vec<PathBuf> {
    let mut dirs = Vec::new();

    if let Some(home) = home_dir() {
        dirs.push(home.join(".opencode").join("bin"));
        dirs.push(home.join(".local").join("bin"));
        dirs.push(home.join(".cargo").join("bin"));
        dirs.push(home.join(".npm-global").join("bin"));
        dirs.push(home.join("node_modules").join(".bin"));
        #[cfg(windows)]
        {
            dirs.push(home.join("AppData").join("Roaming").join("npm"));
            dirs.push(home.join("AppData").join("Local").join("Programs"));
        }
        #[cfg(target_os = "macos")]
        {
            dirs.push(home.join("Applications"));
        }
    }

    #[cfg(not(windows))]
    {
        dirs.push(PathBuf::from("/usr/local/bin"));
        dirs.push(PathBuf::from("/opt/homebrew/bin"));
        dirs.push(PathBuf::from("/usr/bin"));
    }

    #[cfg(windows)]
    {
        if let Ok(appdata) = std::env::var("APPDATA") {
            dirs.push(PathBuf::from(appdata).join("npm"));
        }
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            dirs.push(PathBuf::from(&local).join("Programs"));
        }
        if let Ok(pf) = std::env::var("ProgramFiles") {
            dirs.push(PathBuf::from(pf).join("nodejs"));
        }
    }

    dirs
}

fn resolve_known_location(definition: &RuntimeDefinition, cmd: &str) -> Option<PathBuf> {
    let _ = definition;
    for dir in known_locations() {
        let candidate = dir.join(cmd);
        if is_executable_file(&candidate) {
            return Some(canonicalize_path(&candidate));
        }
        #[cfg(windows)]
        for ext in [".exe", ".cmd", ".bat"] {
            let with_ext = dir.join(format!("{cmd}{ext}"));
            if is_executable_file(&with_ext) {
                return Some(canonicalize_path(&with_ext));
            }
        }
    }
    None
}

fn validate_executable(definition: &RuntimeDefinition, path: &Path) -> bool {
    if !is_executable_file(path) {
        return false;
    }
    if let Some(validate) = definition.validate_executable {
        return validate(path);
    }
    true
}

fn cached_shell_resolved(cmd: &str) -> Option<PathBuf> {
    if !is_safe_binary_name(cmd) {
        return None;
    }

    let key = shell_resolve_env_key();
    let mut cache_guard = SHELL_CACHE.lock().ok()?;
    let needs_refresh = match cache_guard.as_ref() {
        Some(cache) => cache.key != key || cache.resolved_at.elapsed() >= SHELL_RESOLVE_TTL,
        None => true,
    };

    if needs_refresh {
        let names = super::registry::all_binary_names();
        let paths = resolve_via_login_shell(names);
        *cache_guard = Some(ShellCache {
            key,
            resolved_at: Instant::now(),
            paths,
        });
    }

    cache_guard.as_ref()?.paths.get(cmd).cloned()
}

fn shell_resolve_env_key() -> String {
    format!(
        "{}\0{}\0{}",
        std::env::var("PATH").unwrap_or_default(),
        std::env::var("SHELL").unwrap_or_default(),
        std::env::var("HOME").unwrap_or_default(),
    )
}

#[cfg(any(target_os = "macos", target_os = "linux"))]
fn resolve_via_login_shell(names: Vec<String>) -> HashMap<String, PathBuf> {
    let mut out = HashMap::new();
    if names.is_empty() {
        return out;
    }

    let shell = std::env::var("SHELL")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    let Some(shell) = shell else {
        return out;
    };

    let shell_name = Path::new(&shell)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("");
    if !matches!(shell_name, "bash" | "zsh" | "sh" | "dash" | "ksh") {
        return out;
    }

    let safe_names: Vec<String> = names
        .into_iter()
        .filter(|name| is_safe_binary_name(name))
        .collect();
    if safe_names.is_empty() {
        return out;
    }

    let script = build_login_shell_resolve_script(&safe_names);
    let output = std::process::Command::new(&shell)
        .arg("-ilc")
        .arg(script)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output();

    let Ok(output) = output else {
        return out;
    };

    if !output.status.success() && output.stdout.is_empty() {
        return out;
    }

    for line in String::from_utf8_lossy(&output.stdout).lines() {
        let Some((name, path)) = line.split_once('\t') else {
            continue;
        };
        let path = path.trim();
        if !path.starts_with('/') {
            continue;
        }
        let candidate = PathBuf::from(path);
        if is_executable_file(&candidate) {
            out.insert(name.to_string(), canonicalize_path(&candidate));
        }
    }

    out
}

#[cfg(not(any(target_os = "macos", target_os = "linux")))]
fn resolve_via_login_shell(_names: Vec<String>) -> HashMap<String, PathBuf> {
    HashMap::new()
}

#[cfg(any(target_os = "macos", target_os = "linux"))]
fn build_login_shell_resolve_script(names: &[String]) -> String {
    let mut script = String::from("for n in");
    for name in names {
        script.push(' ');
        script.push_str(name);
    }
    script.push_str(
        "; do\n\
         unalias \"$n\" 2>/dev/null\n\
         unset -f \"$n\" 2>/dev/null\n\
         p=$(command -v \"$n\" 2>/dev/null) || continue\n\
         [ -n \"$p\" ] || continue\n\
         case \"$p\" in /*) ;; *) continue ;; esac\n\
         d=$(dirname \"$p\") && f=$(basename \"$p\") && c=$(cd \"$d\" 2>/dev/null && pwd -P) || continue\n\
         printf '%s\\t%s\\n' \"$n\" \"$c/$f\"\n\
         done\n",
    );
    script
}

#[cfg(target_os = "macos")]
fn codex_desktop_bundle_path() -> Option<PathBuf> {
    let mut candidates = vec![
        PathBuf::from("/Applications/ChatGPT.app/Contents/Resources/codex"),
        PathBuf::from("/Applications/Codex.app/Contents/Resources/codex"),
    ];
    if let Ok(home) = std::env::var("HOME") {
        candidates.push(PathBuf::from(format!(
            "{home}/Applications/ChatGPT.app/Contents/Resources/codex"
        )));
        candidates.push(PathBuf::from(format!(
            "{home}/Applications/Codex.app/Contents/Resources/codex"
        )));
    }
    candidates
        .into_iter()
        .find(|path| is_executable_file(path))
        .map(|path| canonicalize_path(&path))
}

#[cfg(not(target_os = "macos"))]
fn codex_desktop_bundle_path() -> Option<PathBuf> {
    None
}

fn home_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(PathBuf::from)
        .or_else(|| std::env::var("USERPROFILE").ok().map(PathBuf::from))
}

pub fn is_executable_file(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::metadata(path)
            .map(|meta| meta.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
    }
    #[cfg(not(unix))]
    {
        true
    }
}

pub fn canonicalize_path(path: &Path) -> PathBuf {
    std::fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf())
}

fn is_safe_binary_name(name: &str) -> bool {
    !name.is_empty()
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.'))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_locations_includes_local_bin() {
        let dirs = known_locations();
        assert!(dirs.iter().any(|d| d.ends_with(".local/bin") || d.ends_with(".local\\bin")));
    }

    #[test]
    fn is_safe_binary_name_rejects_spaces() {
        assert!(is_safe_binary_name("codex"));
        assert!(!is_safe_binary_name("cod ex"));
    }
}
