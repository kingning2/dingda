//! 通过 spawn `license-verifier` 实现的有锁闸门适配器。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use crate::contracts::license::{LicenseActivateRequest, LicenseStatus};
use crate::ports::license::{LicenseError, LicenseGate};
use async_trait::async_trait;
use base64::Engine;
use serde::Deserialize;
use tokio::process::Command;

use super::host_security::LicenseHostSecurity;

/// 授权状态缓存 10 分钟后过期，触发下一次真实校验。
const LICENSE_CACHE_TTL: Duration = Duration::from_secs(10 * 60);

/// 通过 license-verifier 子进程完成机器码与验签的闸门。
///
/// 功能：
///
/// - 校验 verifier 二进制 SHA-256
/// - 异步 spawn + nonce 挑战应答
/// - 激活成功后落盘 `.key` 或 `license.token`
/// - 缓存校验结果并在 10 分钟后过期，兼顾性能与状态同步
///
/// 作者：coisini
/// 创建时间：2026-07-16
pub struct VerifierProcessLicense {
    verifier_path: PathBuf,
    key_path: PathBuf,
    token_path: PathBuf,
    security: LicenseHostSecurity,
    cache: Mutex<Option<CachedLicense>>,
}

#[derive(Clone)]
struct CachedLicense {
    checked_at: Instant,
    status: LicenseStatus,
}

impl VerifierProcessLicense {
    /// 使用已知路径构造闸门（不强制完整性/密钥，供测试）。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    pub fn new(verifier_path: PathBuf, data_dir: PathBuf) -> Self {
        Self {
            verifier_path,
            key_path: data_dir.join("license.key"),
            token_path: data_dir.join("license.token"),
            security: LicenseHostSecurity::from_embedded(),
            cache: Mutex::new(None),
        }
    }

    /// 从环境解析路径，并强制完整性与 attestation 密钥。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    pub fn from_env() -> Result<Self, LicenseError> {
        let verifier_path = resolve_verifier_path()?;
        let security = LicenseHostSecurity::from_embedded();
        security.verify_binary_integrity(&verifier_path)?;
        if !security.has_attest_key() {
            return Err(LicenseError::FailClosed {
                reason: "attestation key not embedded; run `pnpm build:license-verifier` (builds subscription and writes apps/desktop/src-tauri/generated/)"
                    .into(),
            });
        }
        let data_dir = resolve_data_dir()?;
        Self::ensure_dir(&data_dir)?;
        Ok(Self {
            verifier_path,
            key_path: data_dir.join("license.key"),
            token_path: data_dir.join("license.token"),
            security,
            cache: Mutex::new(None),
        })
    }

    async fn run_verifier(&self, args: &[String]) -> Result<(i32, String, String), LicenseError> {
        let started = Instant::now();
        let path_display = self.verifier_path.display().to_string();

        let output = Command::new(&self.verifier_path)
            .args(args)
            .output()
            .await
            .map_err(|cause| LicenseError::SpawnFailed {
                path: path_display.clone(),
                cause: cause.to_string(),
            })?;

        let exit = output.status.code().unwrap_or(2);
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let elapsed_ms = started.elapsed().as_millis();

        info!(
            verifier_path = %path_display,
            exit,
            elapsed_ms,
            args = ?args,
            "授权校验器执行完成"
        );

        Ok((exit, stdout, stderr))
    }

    fn verify_args(&self, nonce: &str) -> Result<Vec<String>, LicenseError> {
        let state_dir = self
            .key_path
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_else(|| PathBuf::from("."));

        let mut args = if self.key_path.is_file() {
            vec![
                "verify".into(),
                "--key-file".into(),
                self.key_path.to_string_lossy().into_owned(),
            ]
        } else if self.token_path.is_file() {
            let token = std::fs::read_to_string(&self.token_path)
                .map_err(|cause| LicenseError::IoFailed {
                    operation: "read".into(),
                    path: self.token_path.display().to_string(),
                    cause: cause.to_string(),
                })?
                .trim()
                .to_string();
            if token.is_empty() {
                return Err(LicenseError::EmptyToken {
                    path: self.token_path.display().to_string(),
                });
            }
            vec!["verify".into(), "--token".into(), token]
        } else {
            return Err(LicenseError::MissingLicenseArtifact);
        };
        args.push("--state-dir".into());
        args.push(state_dir.to_string_lossy().into_owned());
        args.push("--nonce".into());
        args.push(nonce.to_string());
        Ok(args)
    }

    fn parse_verify(
        &self,
        stdout: &str,
        exit: i32,
        nonce: &str,
    ) -> Result<LicenseStatus, LicenseError> {
        if stdout.is_empty() {
            return Err(LicenseError::EmptyVerifierStdout { exit });
        }
        let raw: VerifierJson =
            serde_json::from_str(stdout).map_err(|cause| LicenseError::ParseFailed {
                cause: cause.to_string(),
                stdout: stdout.to_string(),
            })?;

        let attestation = raw.attestation.as_deref().unwrap_or("");
        if attestation.is_empty() {
            return Err(LicenseError::AttestationFailed {
                detail: "missing attestation field in verifier JSON".into(),
            });
        }
        self.security.verify_attestation(
            attestation,
            nonce,
            raw.valid,
            &raw.product,
            raw.token_expired_at,
            &raw.local_machine_code,
        )?;

        Ok(LicenseStatus {
            gate_enabled: true,
            activated: raw.valid && exit == 0,
            reason: raw.reason,
            machine_code: Some(raw.local_machine_code),
            expires_at: Some(raw.token_expired_at),
            product: Some(raw.product),
        })
    }

    fn ensure_dir(path: &Path) -> Result<(), LicenseError> {
        std::fs::create_dir_all(path).map_err(|cause| LicenseError::IoFailed {
            operation: "create_dir".into(),
            path: path.display().to_string(),
            cause: cause.to_string(),
        })
    }

    fn write_bytes(&self, path: &Path, bytes: &[u8]) -> Result<(), LicenseError> {
        if let Some(parent) = path.parent() {
            Self::ensure_dir(parent)?;
        }
        std::fs::write(path, bytes).map_err(|cause| LicenseError::IoFailed {
            operation: "write".into(),
            path: path.display().to_string(),
            cause: cause.to_string(),
        })
    }

    fn remove_license_file(&self, path: &Path) -> Result<(), LicenseError> {
        if !path.exists() {
            return Ok(());
        }
        std::fs::remove_file(path).map_err(|cause| LicenseError::IoFailed {
            operation: "remove".into(),
            path: path.display().to_string(),
            cause: cause.to_string(),
        })
    }

    fn rollback_license_artifacts(&self, primary: LicenseError) -> LicenseError {
        if let Err(cleanup_error) = self.remove_license_file(&self.key_path) {
            warn!(
                path = %self.key_path.display(),
                error = %cleanup_error,
                "激活失败后回滚 license.key 失败"
            );
        }
        if let Err(cleanup_error) = self.remove_license_file(&self.token_path) {
            warn!(
                path = %self.token_path.display(),
                error = %cleanup_error,
                "激活失败后回滚 license.token 失败"
            );
        }
        self.invalidate_cache();
        primary
    }

    fn clear_alternate_artifact(&self, keep_key: bool) -> Result<(), LicenseError> {
        if keep_key {
            self.remove_license_file(&self.token_path)
        } else {
            self.remove_license_file(&self.key_path)
        }
    }

    fn resolve_activate_payload(
        request: &LicenseActivateRequest,
    ) -> Result<ActivatePayload<'_>, LicenseError> {
        let token = request
            .token
            .as_ref()
            .map(|value| value.trim())
            .filter(|value| !value.is_empty());
        let key_b64 = request
            .key_bytes_base64
            .as_ref()
            .map(|value| value.trim())
            .filter(|value| !value.is_empty());

        match (token, key_b64) {
            (Some(token), None) => Ok(ActivatePayload::Token(token)),
            (None, Some(key_b64)) => Ok(ActivatePayload::KeyBase64(key_b64)),
            _ => Err(LicenseError::InvalidActivateRequest),
        }
    }

    fn persist_payload(&self, payload: ActivatePayload<'_>) -> Result<(), LicenseError> {
        match payload {
            ActivatePayload::KeyBase64(raw_b64) => {
                let bytes = base64::engine::general_purpose::STANDARD
                    .decode(raw_b64)
                    .map_err(|cause| LicenseError::KeyDecodeFailed {
                        cause: cause.to_string(),
                    })?;
                self.write_bytes(&self.key_path, &bytes)?;
                self.clear_alternate_artifact(true)?;
            }
            ActivatePayload::Token(token) => {
                self.write_bytes(&self.token_path, token.as_bytes())?;
                self.clear_alternate_artifact(false)?;
            }
        }
        Ok(())
    }

    async fn status_without_artifact(&self, reason: LicenseError) -> LicenseStatus {
        let machine_code = match self.machine_code().await {
            Ok(code) => Some(code),
            Err(error) => {
                warn!(
                    error = %error,
                    "授权状态：未激活时设备码不可用"
                );
                None
            }
        };
        LicenseStatus {
            gate_enabled: true,
            activated: false,
            reason: Some(reason.to_string()),
            machine_code,
            expires_at: None,
            product: None,
        }
    }

    fn invalidate_cache(&self) {
        if let Ok(mut guard) = self.cache.lock() {
            *guard = None;
        }
    }

    fn read_cache(&self) -> Option<LicenseStatus> {
        let guard = self.cache.lock().ok()?;
        let cached = guard.as_ref()?;
        if cached.checked_at.elapsed() > LICENSE_CACHE_TTL {
            return None;
        }
        Some(cached.status.clone())
    }

    fn write_cache(&self, status: LicenseStatus) {
        if let Ok(mut guard) = self.cache.lock() {
            *guard = Some(CachedLicense {
                checked_at: Instant::now(),
                status,
            });
        }
    }
}

enum ActivatePayload<'a> {
    Token(&'a str),
    KeyBase64(&'a str),
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct VerifierJson {
    valid: bool,
    reason: Option<String>,
    product: String,
    local_machine_code: String,
    token_expired_at: i64,
    attestation: Option<String>,
}

#[async_trait]
impl LicenseGate for VerifierProcessLicense {
    async fn status(&self) -> Result<LicenseStatus, LicenseError> {
        if let Some(cached) = self.read_cache() {
            return Ok(cached);
        }
        let nonce = self.security.generate_nonce();
        let args = match self.verify_args(&nonce) {
            Ok(args) => args,
            Err(reason) => {
                let status = self.status_without_artifact(reason).await;
                self.write_cache(status.clone());
                return Ok(status);
            }
        };
        let (exit, stdout, stderr) = self.run_verifier(&args).await?;
        if exit == 2 {
            let detail = if stderr.is_empty() { stdout } else { stderr };
            return Err(LicenseError::VerifierRuntime { exit, detail });
        }
        let status = self.parse_verify(&stdout, exit, &nonce)?;
        self.write_cache(status.clone());
        Ok(status)
    }

    async fn machine_code(&self) -> Result<String, LicenseError> {
        let (exit, stdout, stderr) = self.run_verifier(&["gen-machine-code".to_string()]).await?;
        if exit != 0 {
            let detail = if stderr.is_empty() { stdout } else { stderr };
            return Err(LicenseError::VerifierRuntime { exit, detail });
        }
        if stdout.is_empty() {
            return Err(LicenseError::EmptyVerifierStdout { exit });
        }
        Ok(stdout)
    }

    async fn activate(
        &self,
        request: LicenseActivateRequest,
    ) -> Result<LicenseStatus, LicenseError> {
        let payload = Self::resolve_activate_payload(&request)?;
        self.invalidate_cache();
        if let Err(error) = self.persist_payload(payload) {
            return Err(self.rollback_license_artifacts(error));
        }

        let status = match self.status().await {
            Ok(status) => status,
            Err(error) => return Err(self.rollback_license_artifacts(error)),
        };

        if !status.activated {
            let reason = status
                .reason
                .unwrap_or_else(|| "activation failed".to_string());
            return Err(
                self.rollback_license_artifacts(LicenseError::ActivationRejected { reason })
            );
        }

        info!(
            product = ?status.product,
            expires_at = ?status.expires_at,
            "授权激活成功"
        );
        Ok(status)
    }

    async fn ensure_licensed(&self) -> Result<(), LicenseError> {
        if let Some(cached) = self.read_cache() {
            return if cached.activated {
                Ok(())
            } else {
                Err(LicenseError::NotLicensed {
                    reason: cached
                        .reason
                        .unwrap_or_else(|| "license required".to_string()),
                })
            };
        }

        let status = self.status().await?;
        if status.activated {
            Ok(())
        } else {
            Err(LicenseError::NotLicensed {
                reason: status
                    .reason
                    .unwrap_or_else(|| "license required".to_string()),
            })
        }
    }
}

fn resolve_data_dir() -> Result<PathBuf, LicenseError> {
    if let Ok(path) = std::env::var("DINGDA_LICENSE_DIR") {
        return Ok(PathBuf::from(path));
    }
    let base = std::env::var_os("APPDATA")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .ok_or_else(|| LicenseError::DataDirUnavailable {
            detail: "APPDATA/HOME not set".into(),
        })?;
    Ok(base.join("DingDa"))
}

fn resolve_verifier_path() -> Result<PathBuf, LicenseError> {
    if let Ok(path) = std::env::var("LICENSE_VERIFIER_EXE") {
        let path = PathBuf::from(path);
        if path.is_file() {
            return Ok(path);
        }
        // 环境变量指向缺失文件时继续回退搜索，避免开发机 triple 不一致直接 FailClosed。
        warn!(
            path = %path.display(),
            "LICENSE_VERIFIER_EXE 已设置但文件不存在，回退到内置查找"
        );
    }

    let search_dirs = verifier_search_dirs();
    for dir in &search_dirs {
        for name in verifier_candidate_names() {
            let candidate = dir.join(&name);
            if candidate.is_file() {
                info!(path = %candidate.display(), "已解析授权校验器");
                return Ok(candidate);
            }
        }
    }

    Err(LicenseError::VerifierNotFound {
        detail: format!(
            "looked for {} under {:?} (Windows builds use MSVC-named verifier only)",
            bundled_verifier_filename(),
            search_dirs
        ),
    })
}

/// Verifier 搜索目录：可执行文件旁、src-tauri/binaries、release 产物。
fn verifier_search_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();

    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            dirs.push(parent.to_path_buf());
        }
    } else {
        warn!("无法获取当前可执行文件路径，无法定位授权校验器");
        dirs.push(PathBuf::from("."));
    }

    dirs.push(PathBuf::from("apps/desktop/src-tauri/binaries"));
    dirs.push(PathBuf::from("subscription/target/release"));
    dirs.push(PathBuf::from("target/release"));

    if let Ok(mut dir) = std::env::current_dir() {
        for _ in 0..6 {
            let candidate = dir.join("apps/desktop/src-tauri/binaries");
            if candidate.is_dir() {
                dirs.push(candidate);
            }
            if !dir.pop() {
                break;
            }
        }
    }

    dirs
}

/// 按编译 triple 生成候选文件名（Windows 仅 MSVC 命名）。
fn verifier_candidate_names() -> Vec<String> {
    let mut names = Vec::new();
    names.push(bundled_verifier_filename());
    // 本机开发：若 TARGET 被映射为 msvc，仍兼容常见 x86_64 产物名。
    if cfg!(target_os = "windows") {
        let triple = env!("DINGDA_LICENSE_TARGET_TRIPLE");
        if triple != "x86_64-pc-windows-msvc" {
            names.push("license-verifier-x86_64-pc-windows-msvc.exe".into());
        }
    }
    names.push(verifier_bin_name().to_string());
    names
}

fn verifier_bin_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "license-verifier.exe"
    } else {
        "license-verifier"
    }
}

fn bundled_verifier_filename() -> String {
    let triple = env!("DINGDA_LICENSE_TARGET_TRIPLE");
    let base = format!("license-verifier-{triple}");
    if cfg!(target_os = "windows") {
        format!("{base}.exe")
    } else {
        base
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn verify_args_prefers_key_file_and_appends_nonce() {
        let data_dir =
            std::env::temp_dir().join(format!("dingda-license-test-key-{}", std::process::id()));
        let _ = fs::remove_dir_all(&data_dir);
        fs::create_dir_all(&data_dir).expect("mkdir");
        let key_path = data_dir.join("license.key");
        fs::write(&key_path, b"key").expect("write key");

        let gate = VerifierProcessLicense::new(PathBuf::from("unused"), data_dir.clone());
        let args = gate.verify_args("nonce-1").expect("args");
        assert_eq!(args[0], "verify");
        assert_eq!(args[1], "--key-file");
        assert_eq!(args[2], key_path.to_string_lossy());
        assert_eq!(args[3], "--state-dir");
        assert_eq!(args[4], data_dir.to_string_lossy());
        assert_eq!(args[5], "--nonce");
        assert_eq!(args[6], "nonce-1");

        let _ = fs::remove_dir_all(&data_dir);
    }

    #[test]
    fn resolve_activate_payload_rejects_both_or_neither() {
        assert!(matches!(
            VerifierProcessLicense::resolve_activate_payload(&LicenseActivateRequest {
                token: None,
                key_bytes_base64: None,
            }),
            Err(LicenseError::InvalidActivateRequest)
        ));
        assert!(matches!(
            VerifierProcessLicense::resolve_activate_payload(&LicenseActivateRequest {
                token: Some("a".into()),
                key_bytes_base64: Some("b".into()),
            }),
            Err(LicenseError::InvalidActivateRequest)
        ));
    }

    #[test]
    fn parse_verify_rejects_missing_attestation() {
        let gate = VerifierProcessLicense::new(
            PathBuf::from("unused"),
            std::env::temp_dir().join("dingda-license-test-parse"),
        );
        let stdout = r#"{
            "valid": true,
            "reason": null,
            "product": "dingda",
            "localMachineCode": "abc",
            "tokenExpiredAt": 1
        }"#;
        let err = gate
            .parse_verify(stdout, 0, "n")
            .expect_err("missing attestation");
        assert!(matches!(err, LicenseError::AttestationFailed { .. }));
    }
}
