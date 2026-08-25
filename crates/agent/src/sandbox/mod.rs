//! 网络沙盒 — 出站 HTTP 的 fail-closed 隔离（参考 deepseek-harness `ctx.sandbox` 精神）。
//!
//! 本次不 wrap 进程 argv（Windows ACL / bwrap），只约束 AI 联网工具的 URL / 主机 /
//! 超时 / 响应体积，防止 SSRF 与无限下载。

use std::collections::HashSet;
use std::net::IpAddr;
use std::time::Duration;

use thiserror::Error;
use url::Url;

/// 沙盒拒绝原因（fail-closed：无法判定则拒绝）。
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum SandboxError {
    #[error("sandbox: invalid url: {0}")]
    InvalidUrl(String),
    #[error("sandbox: scheme `{0}` not allowed (https only)")]
    SchemeDenied(String),
    #[error("sandbox: host `{0}` not in allowlist")]
    HostDenied(String),
    #[error("sandbox: host `{0}` resolves to blocked address class")]
    AddressDenied(String),
    #[error("sandbox: request timed out")]
    Timeout,
    #[error("sandbox: response exceeds max bytes ({0})")]
    ResponseTooLarge(usize),
    #[error("sandbox: unavailable: {0}")]
    Unavailable(String),
}

/// 单次出站请求的网络策略（per-call，与 harness SandboxPolicy 同构）。
#[derive(Debug, Clone)]
pub struct NetworkPolicy {
    /// 允许的主机名（小写）。空 = 拒绝全部（fail-closed）。
    pub allowed_hosts: HashSet<String>,
    pub timeout: Duration,
    pub max_response_bytes: usize,
    /// 是否拒绝字面量私网 / 环回 / 链路本地 IP。
    pub block_private_ips: bool,
}

impl Default for NetworkPolicy {
    fn default() -> Self {
        Self {
            allowed_hosts: HashSet::new(),
            timeout: Duration::from_secs(15),
            max_response_bytes: 512 * 1024,
            block_private_ips: true,
        }
    }
}

impl NetworkPolicy {
    pub fn with_hosts(hosts: impl IntoIterator<Item = impl Into<String>>) -> Self {
        let mut policy = Self::default();
        policy.allowed_hosts = hosts
            .into_iter()
            .map(|h| h.into().trim().to_lowercase())
            .filter(|h| !h.is_empty())
            .collect();
        policy
    }
}

/// 网络沙盒：校验 URL，并提供受约束的 GET。
#[derive(Debug, Clone)]
pub struct NetworkSandbox {
    policy: NetworkPolicy,
}

impl NetworkSandbox {
    pub fn new(policy: NetworkPolicy) -> Self {
        Self { policy }
    }

    pub fn policy(&self) -> &NetworkPolicy {
        &self.policy
    }

    /// 校验 URL 是否允许出站。无法判定时拒绝。
    pub fn check_url(&self, raw: &str) -> Result<Url, SandboxError> {
        let url = Url::parse(raw).map_err(|e| SandboxError::InvalidUrl(e.to_string()))?;
        if url.scheme() != "https" {
            return Err(SandboxError::SchemeDenied(url.scheme().to_string()));
        }
        let host = url
            .host_str()
            .ok_or_else(|| SandboxError::InvalidUrl("missing host".into()))?
            .to_lowercase();

        if self.policy.allowed_hosts.is_empty() {
            return Err(SandboxError::Unavailable(
                "no allowed hosts configured".into(),
            ));
        }
        if !self.policy.allowed_hosts.contains(&host) {
            return Err(SandboxError::HostDenied(host));
        }

        if self.policy.block_private_ips {
            if let Ok(ip) = host.parse::<IpAddr>() {
                if is_blocked_ip(ip) {
                    return Err(SandboxError::AddressDenied(host));
                }
            }
        }

        Ok(url)
    }

    /// 经沙盒约束的 HTTPS GET，返回 UTF-8 文本（超限截断并报错）。
    pub async fn get_text(&self, raw_url: &str) -> Result<String, SandboxError> {
        let url = self.check_url(raw_url)?;
        let client = reqwest::Client::builder()
            .timeout(self.policy.timeout)
            .redirect(reqwest::redirect::Policy::none())
            .user_agent("DingDa-Agent-WebSearch/0.1")
            .build()
            .map_err(|e| SandboxError::Unavailable(e.to_string()))?;

        let response = client.get(url).send().await.map_err(|e| {
            if e.is_timeout() {
                SandboxError::Timeout
            } else {
                SandboxError::Unavailable(e.to_string())
            }
        })?;

        if !response.status().is_success() {
            return Err(SandboxError::Unavailable(format!(
                "HTTP {}",
                response.status()
            )));
        }

        let bytes = response
            .bytes()
            .await
            .map_err(|e| SandboxError::Unavailable(e.to_string()))?;
        if bytes.len() > self.policy.max_response_bytes {
            return Err(SandboxError::ResponseTooLarge(
                self.policy.max_response_bytes,
            ));
        }
        String::from_utf8(bytes.to_vec())
            .map_err(|e| SandboxError::Unavailable(format!("utf8: {e}")))
    }
}

fn is_blocked_ip(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => {
            v4.is_loopback()
                || v4.is_private()
                || v4.is_link_local()
                || v4.is_broadcast()
                || v4.is_unspecified()
                || v4.octets()[0] == 169 && v4.octets()[1] == 254
        }
        IpAddr::V6(v6) => {
            v6.is_loopback()
                || v6.is_unique_local()
                || v6.is_unicast_link_local()
                || v6.is_unspecified()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn denies_http_and_private_literal() {
        let sandbox = NetworkSandbox::new(NetworkPolicy::with_hosts(["api.duckduckgo.com"]));
        assert!(matches!(
            sandbox.check_url("http://api.duckduckgo.com/"),
            Err(SandboxError::SchemeDenied(_))
        ));
        let sandbox = NetworkSandbox::new(NetworkPolicy::with_hosts(["127.0.0.1"]));
        assert!(matches!(
            sandbox.check_url("https://127.0.0.1/"),
            Err(SandboxError::AddressDenied(_))
        ));
    }

    #[test]
    fn allowlist_enforced() {
        let sandbox = NetworkSandbox::new(NetworkPolicy::with_hosts(["api.duckduckgo.com"]));
        assert!(sandbox.check_url("https://api.duckduckgo.com/?q=1").is_ok());
        assert!(matches!(
            sandbox.check_url("https://evil.example/"),
            Err(SandboxError::HostDenied(_))
        ));
    }

    #[test]
    fn empty_allowlist_fail_closed() {
        let sandbox = NetworkSandbox::new(NetworkPolicy::default());
        assert!(matches!(
            sandbox.check_url("https://api.duckduckgo.com/"),
            Err(SandboxError::Unavailable(_))
        ));
    }
}
