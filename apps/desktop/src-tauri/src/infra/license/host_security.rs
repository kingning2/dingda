//! License verifier 主机侧 attestation / 完整性工具。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::ports::license::LicenseError;
use hmac::{Hmac, Mac};
use sha2::{Digest, Sha256};

type HmacSha256 = Hmac<Sha256>;

/// 主机侧 license 安全辅助。
///
/// 功能：
///
/// - 计算 / 校验 verifier 文件 SHA-256
/// - 生成 nonce 并校验 HMAC attestation
///
/// 作者：coisini
/// 创建时间：2026-07-16
pub struct LicenseHostSecurity {
    attest_key: Vec<u8>,
    expected_sha256: String,
}

impl LicenseHostSecurity {
    /// 从编译期嵌入的环境常量构造。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 返回值
    ///
    /// 返回 [`LicenseHostSecurity`]；attestation 密钥可为空（仅开发态）。
    pub fn from_embedded() -> Self {
        Self {
            attest_key: decode_hex(env!("DINGDA_LICENSE_ATTEST_KEY_HEX").trim())
                .unwrap_or_default(),
            expected_sha256: env!("DINGDA_LICENSE_VERIFIER_SHA256").trim().to_string(),
        }
    }

    /// 使用显式密钥构造（单测）。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    pub fn new(attest_key: Vec<u8>, expected_sha256: impl Into<String>) -> Self {
        Self {
            attest_key,
            expected_sha256: expected_sha256.into(),
        }
    }

    /// 是否已嵌入 attestation 密钥。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    pub fn has_attest_key(&self) -> bool {
        !self.attest_key.is_empty()
    }

    /// 校验 verifier 二进制哈希（期望为空则跳过并打日志由调用方处理）。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    ///
    /// # 参数
    ///
    /// * `path` - verifier 可执行文件路径
    ///
    /// # 返回值
    ///
    /// 通过返回 `Ok(())`；不匹配返回 [`LicenseError::IntegrityFailed`]。
    pub fn verify_binary_integrity(&self, path: &Path) -> Result<(), LicenseError> {
        if self.expected_sha256.is_empty() {
            return Ok(());
        }
        let bytes = std::fs::read(path).map_err(|cause| LicenseError::IoFailed {
            operation: "read".into(),
            path: path.display().to_string(),
            cause: cause.to_string(),
        })?;
        let actual = hex_sha256(&bytes);
        if !actual.eq_ignore_ascii_case(&self.expected_sha256) {
            return Err(LicenseError::IntegrityFailed {
                path: path.display().to_string(),
                expected: self.expected_sha256.clone(),
                actual,
            });
        }
        Ok(())
    }

    /// 生成挑战 nonce。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    pub fn generate_nonce(&self) -> String {
        let mut hasher = Sha256::new();
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        hasher.update(nanos.to_le_bytes());
        hasher.update(std::process::id().to_le_bytes());
        hasher.update(b"dingda-nonce");
        hex_encode(hasher.finalize())
    }

    /// 校验 verifier 返回的 attestation。
    ///
    /// 作者：coisini
    /// 创建时间：2026-07-16
    pub fn verify_attestation(
        &self,
        attestation_hex: &str,
        nonce: &str,
        valid: bool,
        product: &str,
        token_expired_at: i64,
        local_machine_code: &str,
    ) -> Result<(), LicenseError> {
        if self.attest_key.is_empty() {
            return Err(LicenseError::AttestationFailed {
                detail: "attestation key not embedded; run subscription build / pnpm build:license-verifier"
                    .into(),
            });
        }
        let expected =
            self.sign_attestation(nonce, valid, product, token_expired_at, local_machine_code)?;
        if expected.eq_ignore_ascii_case(attestation_hex.trim()) {
            Ok(())
        } else {
            Err(LicenseError::AttestationFailed {
                detail: "HMAC mismatch".into(),
            })
        }
    }

    fn sign_attestation(
        &self,
        nonce: &str,
        valid: bool,
        product: &str,
        token_expired_at: i64,
        local_machine_code: &str,
    ) -> Result<String, LicenseError> {
        let payload = format!("{nonce}|{valid}|{product}|{token_expired_at}|{local_machine_code}");
        let mut mac = HmacSha256::new_from_slice(&self.attest_key).map_err(|error| {
            LicenseError::AttestationFailed {
                detail: format!("HMAC init failed: {error}"),
            }
        })?;
        mac.update(payload.as_bytes());
        Ok(hex_encode(mac.finalize().into_bytes()))
    }
}

fn hex_sha256(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex_encode(hasher.finalize())
}

fn hex_encode(bytes: impl AsRef<[u8]>) -> String {
    bytes
        .as_ref()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn decode_hex(input: &str) -> Result<Vec<u8>, LicenseError> {
    if input.is_empty() {
        return Ok(Vec::new());
    }
    if !input.len().is_multiple_of(2) {
        return Err(LicenseError::AttestationFailed {
            detail: "hex length must be even".into(),
        });
    }
    (0..input.len())
        .step_by(2)
        .map(|index| {
            u8::from_str_radix(&input[index..index + 2], 16).map_err(|error| {
                LicenseError::AttestationFailed {
                    detail: format!("invalid hex: {error}"),
                }
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn attestation_roundtrip() {
        let security = LicenseHostSecurity::new(b"test-key-32-bytes-pad-pad-pad!!".to_vec(), "");
        let nonce = "abc";
        let hex = security
            .sign_attestation(nonce, true, "dingda", 1, "machine")
            .expect("sign");
        security
            .verify_attestation(&hex, nonce, true, "dingda", 1, "machine")
            .expect("verify");
    }

    #[test]
    fn integrity_mismatch_detected() {
        let dir = std::env::temp_dir().join(format!("od-integrity-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let path = dir.join("fake.exe");
        std::fs::write(&path, b"hello").expect("write");
        let actual = hex_sha256(b"hello");
        let security = LicenseHostSecurity::new(Vec::new(), "deadbeef".to_string());
        let err = security
            .verify_binary_integrity(&path)
            .expect_err("mismatch");
        assert!(matches!(err, LicenseError::IntegrityFailed { .. }));
        let security_ok = LicenseHostSecurity::new(Vec::new(), actual);
        security_ok.verify_binary_integrity(&path).expect("match");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
