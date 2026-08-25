//! AI 配置 Tauri commands。
//!
//! @author coisini
//! @created 2026-08-11

use crate::contracts::contracts::{AiIpcConfigRequest, AiIpcConfigResponse};
use crate::contracts::DingDaResult;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::cmd::IpcResponse;
use crate::config::ConfigStore;

/// 单币种余额条目。
///
/// @author Xiaoman
/// @created 2026-08-20
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiBalanceInfoDto {
    /// 币种（CNY / USD）。
    pub currency: String,
    /// 总可用余额。
    pub total_balance: String,
    /// 赠金余额。
    pub granted_balance: String,
    /// 充值余额。
    pub topped_up_balance: String,
}

/// API Key 探测 / 余额查询结果。
///
/// @author coisini
/// @created 2026-08-11
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiApiKeyTestResult {
    /// 是否可用。
    pub ok: bool,
    /// 结果说明。
    pub message: String,
}

/// 账号余额查询结果。
///
/// @author Xiaoman
/// @created 2026-08-20
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiAccountBalanceResult {
    /// 是否查询成功。
    pub ok: bool,
    /// 余额是否足够调用 API。
    pub is_available: bool,
    /// 各币种余额。
    pub balances: Vec<AiBalanceInfoDto>,
    /// 失败时的可读说明。
    pub message: String,
}

#[derive(Debug, Deserialize)]
struct BalanceApiResponse {
    is_available: Option<bool>,
    balance_infos: Option<Vec<AiBalanceInfoDto>>,
}

/// 读取 AI 配置 IPC。
///
/// @author coisini
/// @created 2026-08-11
#[tauri::command]
pub async fn ai_config_get(
    state: tauri::State<'_, Arc<ConfigStore>>,
) -> DingDaResult<IpcResponse<AiIpcConfigResponse>> {
    let result = state.ai_get().await?;
    Ok(IpcResponse::ok(result))
}

/// 写入 AI 配置 IPC（整体替换）。
///
/// @author coisini
/// @created 2026-08-11
#[tauri::command]
pub async fn ai_config_set(
    state: tauri::State<'_, Arc<ConfigStore>>,
    config: AiIpcConfigRequest,
) -> DingDaResult<IpcResponse<AiIpcConfigResponse>> {
    let result = state.ai_set(config).await?;
    Ok(IpcResponse::ok(result))
}

/// 探测 OpenAI 兼容 API Key（DeepSeek 走 `/user/balance`）。
///
/// @author coisini
/// @created 2026-08-11
#[tauri::command]
pub async fn ai_test_api_key(
    base_url: String,
    api_key: String,
    kind: Option<String>,
) -> DingDaResult<IpcResponse<AiApiKeyTestResult>> {
    match probe_api_key(&base_url, &api_key, kind.as_deref()).await {
        Ok(result) => Ok(IpcResponse::ok(result)),
        Err(error) => Err(error),
    }
}

/// 查询账号余额（DeepSeek `/user/balance`）。
///
/// @author Xiaoman
/// @created 2026-08-20
#[tauri::command]
pub async fn ai_account_balance(
    base_url: String,
    api_key: String,
) -> DingDaResult<IpcResponse<AiAccountBalanceResult>> {
    Ok(IpcResponse::ok(
        fetch_account_balance(&base_url, &api_key).await?,
    ))
}

fn uses_deepseek_balance(kind: Option<&str>, base_url: &str) -> bool {
    matches!(kind, Some("deepseek")) || base_url.to_ascii_lowercase().contains("deepseek.com")
}

fn openai_compatible_root(base_url: &str) -> String {
    let base = base_url.trim().trim_end_matches('/');
    if base.ends_with("/v1") || base.ends_with("/v2") || base.ends_with("/v3") {
        return base.to_string();
    }
    format!("{base}/v1")
}

async fn probe_api_key(
    base_url: &str,
    api_key: &str,
    kind: Option<&str>,
) -> DingDaResult<AiApiKeyTestResult> {
    if uses_deepseek_balance(kind, base_url) {
        let result = fetch_account_balance(base_url, api_key).await?;
        return Ok(AiApiKeyTestResult {
            ok: result.ok,
            message: if result.ok {
                "API Key 可用".to_string()
            } else {
                result.message
            },
        });
    }

    let trimmed_key = api_key.trim();
    if trimmed_key.is_empty() {
        return Ok(AiApiKeyTestResult {
            ok: false,
            message: "API Key 为空".to_string(),
        });
    }

    let url = format!("{}/models", openai_compatible_root(base_url));
    let response = reqwest::Client::new()
        .get(url)
        .header("Authorization", format!("Bearer {trimmed_key}"))
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
        .map_err(|error| format!("请求失败: {error}"))?;

    if response.status().is_success() {
        return Ok(AiApiKeyTestResult {
            ok: true,
            message: "API Key 可用".to_string(),
        });
    }

    Ok(AiApiKeyTestResult {
        ok: false,
        message: format!("HTTP {}", response.status()),
    })
}

async fn fetch_account_balance(
    base_url: &str,
    api_key: &str,
) -> DingDaResult<AiAccountBalanceResult> {
    let trimmed_key = api_key.trim();
    if trimmed_key.is_empty() {
        return Ok(AiAccountBalanceResult {
            ok: false,
            is_available: false,
            balances: Vec::new(),
            message: "API Key 为空".to_string(),
        });
    }

    let url = format!("{}/user/balance", base_url.trim_end_matches('/'));
    let response = reqwest::Client::new()
        .get(url)
        .header("Authorization", format!("Bearer {trimmed_key}"))
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
        .map_err(|error| format!("请求失败: {error}"))?;

    if !response.status().is_success() {
        return Ok(AiAccountBalanceResult {
            ok: false,
            is_available: false,
            balances: Vec::new(),
            message: format!("HTTP {}", response.status()),
        });
    }

    let body: BalanceApiResponse = response
        .json()
        .await
        .map_err(|error| format!("解析失败: {error}"))?;

    let balances = body.balance_infos.unwrap_or_default();
    let is_available = body.is_available.unwrap_or(!balances.is_empty());
    let ok = !balances.is_empty();

    Ok(AiAccountBalanceResult {
        ok,
        is_available,
        message: if ok {
            "ok".to_string()
        } else {
            "未返回余额信息".to_string()
        },
        balances,
    })
}
