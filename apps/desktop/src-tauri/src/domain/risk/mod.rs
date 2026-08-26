//! 风控日志 — 滑块/风控事件日志查询与配置。
//!
//! 对齐 Python 版 `/api/v1/risk-control-logs`：
//! - 分页查询（账号 / 日期 / 处理状态 / 调用类型 / 调用用户筛选）；
//! - 当日成功率统计（总体 / 本机 / 远程 + 处理中计数）；
//! - 清空日志 / 清空处理中日志；
//! - 远程过滑块全局配置与本机滑块处理开关的存取。

use crate::contracts::DingDaResult;
use serde::{Deserialize, Serialize};

/// 风控日志条目（对齐 Python 版 `RiskLog`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskLogItem {
    pub id: i64,
    pub owner_id: i64,
    /// 账号标识（原前端 cookie_id）。
    pub account_id: String,
    /// 事件类型。
    pub risk_type: String,
    /// 事件描述。
    pub message: String,
    #[serde(default)]
    pub processing_result: String,
    #[serde(default)]
    pub processing_status: String,
    #[serde(default)]
    pub captcha_engine: Option<String>,
    #[serde(default)]
    pub call_type: Option<String>,
    #[serde(default)]
    pub call_user: Option<String>,
    #[serde(default)]
    pub error_message: Option<String>,
    #[serde(default)]
    pub created_at: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
}

/// 日志查询条件。
#[derive(Debug, Clone, Default)]
pub struct RiskLogQuery {
    pub page: u32,
    pub page_size: u32,
    pub account_id: String,
    pub start_date: String,
    pub end_date: String,
    pub processing_status: String,
    pub call_type: String,
    pub call_user: String,
}

/// 分页结果。
#[derive(Debug, Clone, Serialize)]
pub struct RiskLogPage {
    pub data: Vec<RiskLogItem>,
    pub total: u32,
    pub page: u32,
    pub page_size: u32,
    pub total_pages: u32,
}

/// 当日成功率（总体 / 本机 / 远程三维度）。
#[derive(Debug, Clone, Default, Serialize)]
pub struct RiskTodaySuccessRate {
    pub date: String,
    pub total: u32,
    pub success: u32,
    pub rate: u32,
    pub local_total: u32,
    pub local_success: u32,
    pub local_rate: u32,
    pub remote_total: u32,
    pub remote_success: u32,
    pub remote_rate: u32,
    pub processing: u32,
    pub local_processing: u32,
    pub remote_processing: u32,
}

/// 远程过滑块全局配置 + 本机滑块处理开关（对齐 Python `system_settings`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskConfig {
    #[serde(default)]
    pub remote_url: String,
    #[serde(default)]
    pub remote_secret: String,
    #[serde(default)]
    pub pass_cookies: bool,
    #[serde(default = "default_true")]
    pub block_remote_calls: bool,
    #[serde(default = "default_weight")]
    pub local_weight: u32,
    #[serde(default = "default_weight")]
    pub remote_weight: u32,
    #[serde(default = "default_processing_max")]
    pub remote_processing_max: u32,
    #[serde(default = "default_cooldown")]
    pub remote_cooldown_seconds: u32,
    /// 本机滑块不处理开关。
    #[serde(default)]
    pub local_slider_disabled: bool,
}

fn default_true() -> bool {
    true
}
fn default_weight() -> u32 {
    1
}
fn default_processing_max() -> u32 {
    20
}
fn default_cooldown() -> u32 {
    600
}

impl Default for RiskConfig {
    fn default() -> Self {
        Self {
            remote_url: String::new(),
            remote_secret: String::new(),
            pass_cookies: false,
            block_remote_calls: true,
            local_weight: 1,
            remote_weight: 1,
            remote_processing_max: 20,
            remote_cooldown_seconds: 600,
            local_slider_disabled: false,
        }
    }
}

/// 风控存储 Port。
pub trait RiskStore: Send + Sync {
    /// 分页查询（按归属）。
    fn list_logs(&self, owner_id: i64, query: &RiskLogQuery) -> DingDaResult<Vec<RiskLogItem>>;

    /// 清空日志（account_id 为空则全部）。
    fn clear_logs(&self, owner_id: i64, account_id: &str) -> DingDaResult<()>;

    /// 清空处理中日志。
    fn clear_processing(&self, owner_id: i64) -> DingDaResult<()>;

    /// 读取配置。
    fn get_config(&self, owner_id: i64) -> DingDaResult<RiskConfig>;

    /// 保存配置。
    fn save_config(&self, owner_id: i64, config: &RiskConfig) -> DingDaResult<()>;

    /// 追加风控日志（`id == 0` 时存储层自动分配）。
    fn append_log(&self, log: RiskLogItem) -> DingDaResult<RiskLogItem>;

    /// 按 id 更新已有风控日志（用于过滑块结果回写）。
    fn update_log(&self, log: &RiskLogItem) -> DingDaResult<()>;
}

/// 风控服务。
pub struct RiskService<'a> {
    store: &'a dyn RiskStore,
}

impl<'a> RiskService<'a> {
    pub fn new(store: &'a dyn RiskStore) -> Self {
        Self { store }
    }

    /// 分页查询（page 从 1 起，page_size 钳制 1-200）。
    pub fn list(&self, owner_id: i64, query: &RiskLogQuery) -> DingDaResult<RiskLogPage> {
        let page = query.page.max(1);
        let page_size = query.page_size.clamp(1, 200);
        let all = self.store.list_logs(owner_id, query)?;
        let total = all.len() as u32;
        let total_pages = if total == 0 {
            0
        } else {
            total.div_ceil(page_size)
        };
        let start = ((page - 1) * page_size) as usize;
        let data = all
            .into_iter()
            .skip(start)
            .take(page_size as usize)
            .collect();
        Ok(RiskLogPage {
            data,
            total,
            page,
            page_size,
            total_pages,
        })
    }

    /// 当日成功率（按 created_at 日期前缀过滤）。
    pub fn today_success_rate(
        &self,
        owner_id: i64,
        date: &str,
    ) -> DingDaResult<RiskTodaySuccessRate> {
        let all = self.store.list_logs(
            owner_id,
            &RiskLogQuery {
                start_date: date.to_string(),
                end_date: date.to_string(),
                ..Default::default()
            },
        )?;
        let mut rate = RiskTodaySuccessRate {
            date: date.to_string(),
            ..Default::default()
        };
        for log in &all {
            let is_remote = log.call_type.as_deref() == Some("remote");
            let is_success = log.processing_status == "success";
            let is_processing = log.processing_status == "processing";
            rate.total += 1;
            if is_success {
                rate.success += 1;
            }
            if is_processing {
                rate.processing += 1;
            }
            if is_remote {
                rate.remote_total += 1;
                if is_success {
                    rate.remote_success += 1;
                }
                if is_processing {
                    rate.remote_processing += 1;
                }
            } else {
                rate.local_total += 1;
                if is_success {
                    rate.local_success += 1;
                }
                if is_processing {
                    rate.local_processing += 1;
                }
            }
        }
        rate.rate = pct(rate.success, rate.total);
        rate.local_rate = pct(rate.local_success, rate.local_total);
        rate.remote_rate = pct(rate.remote_success, rate.remote_total);
        Ok(rate)
    }

    /// 清空日志（account_id 为空则全部）。
    pub fn clear(&self, owner_id: i64, account_id: &str) -> DingDaResult<()> {
        self.store.clear_logs(owner_id, account_id)
    }

    /// 清空处理中日志。
    pub fn clear_processing(&self, owner_id: i64) -> DingDaResult<()> {
        self.store.clear_processing(owner_id)
    }

    /// 读取配置。
    pub fn get_config(&self, owner_id: i64) -> DingDaResult<RiskConfig> {
        self.store.get_config(owner_id)
    }

    /// 保存配置（远程 URL 校验：禁止填写 Token 获取专用域名）。
    pub fn save_config(&self, owner_id: i64, config: &RiskConfig) -> DingDaResult<()> {
        const TOKEN_API_ONLY_DOMAINS: [&str; 2] = ["api.xianyusite.shop", "api.zhinianblog.cn"];
        let lowered = config.remote_url.trim().to_lowercase();
        if TOKEN_API_ONLY_DOMAINS
            .iter()
            .any(|domain| lowered.contains(domain))
        {
            return Err(
                "该URL是Token获取接口域名，需在「系统设置-Token获取方式」中填写"
                    .to_string()
                    .into(),
            );
        }
        self.store.save_config(owner_id, config)
    }

    /// 记录闲鱼 IM / mtop 风控拦截事件。
    ///
    /// 同账号已有 `processing` 日志时复用并刷新，避免 WS 重试刷出多条「处理中」。
    /// 原始错误不入 `error_message`（展示在「处理结果 / 失败原因」终态字段）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    pub fn record_im_risk(
        &self,
        owner_id: i64,
        account_id: &str,
        source: &str,
        detail: &str,
    ) -> DingDaResult<RiskLogItem> {
        let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let risk_type = if detail.contains("captcha") || detail.contains("punish") {
            "slider".to_string()
        } else {
            "rgv587".to_string()
        };
        let message = format!("{source}：触发闲鱼风控");

        let processing = self.store.list_logs(
            owner_id,
            &RiskLogQuery {
                account_id: account_id.to_string(),
                processing_status: "processing".to_string(),
                ..Default::default()
            },
        )?;
        if let Some(mut log) = processing.into_iter().max_by_key(|item| item.id) {
            log.risk_type = risk_type;
            log.message = message;
            log.updated_at = Some(now);
            self.store.update_log(&log)?;
            return Ok(log);
        }

        let log = RiskLogItem {
            id: 0,
            owner_id,
            account_id: account_id.to_string(),
            risk_type,
            message,
            processing_result: String::new(),
            processing_status: "processing".to_string(),
            captcha_engine: Some("playwright".to_string()),
            call_type: Some("local".to_string()),
            call_user: None,
            error_message: None,
            created_at: Some(now),
            updated_at: None,
        };
        self.store.append_log(log)
    }

    /// 记录本机过滑块结果（成功 / 失败）。
    ///
    /// 同账号所有 `processing` 日志一并更新为终态；没有则追加新日志。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-21
    ///
    /// # 参数
    /// - `owner_id` — 归属用户
    /// - `account_id` — 账号 id
    /// - `success` — 是否过滑块成功
    /// - `detail` — 失败时的短错误；成功可传空
    pub fn record_slider_outcome(
        &self,
        owner_id: i64,
        account_id: &str,
        success: bool,
        detail: &str,
    ) -> DingDaResult<RiskLogItem> {
        let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let status = if success { "success" } else { "failed" };
        let processing_result = if success {
            "滑块验证通过，Cookie 已续期".to_string()
        } else {
            format!("滑块验证失败：{}", humanize_failure_detail(detail))
        };
        let message = if success {
            "滑块验证通过".to_string()
        } else {
            "滑块验证失败".to_string()
        };
        let error_message = if success {
            None
        } else {
            Some(humanize_failure_detail(detail))
        };

        let processing = self.store.list_logs(
            owner_id,
            &RiskLogQuery {
                account_id: account_id.to_string(),
                processing_status: "processing".to_string(),
                ..Default::default()
            },
        )?;
        if !processing.is_empty() {
            let mut last = None;
            for mut log in processing {
                log.risk_type = "slider".to_string();
                log.message = message.clone();
                log.processing_result = processing_result.clone();
                log.processing_status = status.to_string();
                log.captcha_engine = Some("playwright".to_string());
                log.call_type = Some("local".to_string());
                log.error_message = error_message.clone();
                log.updated_at = Some(now.clone());
                self.store.update_log(&log)?;
                last = Some(log);
            }
            return Ok(last.expect("processing 非空"));
        }

        let log = RiskLogItem {
            id: 0,
            owner_id,
            account_id: account_id.to_string(),
            risk_type: "slider".to_string(),
            message,
            processing_result,
            processing_status: status.to_string(),
            captcha_engine: Some("playwright".to_string()),
            call_type: Some("local".to_string()),
            call_user: None,
            error_message,
            created_at: Some(now),
            updated_at: None,
        };
        self.store.append_log(log)
    }
}

/// 截断过长文本（按 Unicode 字符计）。
fn truncate_detail(detail: &str, max_chars: usize) -> String {
    if detail.chars().count() <= max_chars {
        return detail.to_string();
    }
    format!("{}…", detail.chars().take(max_chars).collect::<String>())
}

/// 将原始协议错误转为可读失败原因（避免整段 JSON 进表格）。
fn humanize_failure_detail(detail: &str) -> String {
    let trimmed = detail.trim();
    if trimmed.is_empty() {
        return "未知错误".to_string();
    }
    if trimmed.contains("RGV587") || trimmed.contains("被挤爆") || trimmed.contains("USER_VALIDATE")
    {
        return "闲鱼风控拦截，滑块验证未通过".to_string();
    }
    if trimmed.contains("Sidecar 未就绪") || trimmed.contains("Sidecar") {
        return truncate_detail(trimmed, 120);
    }
    if trimmed.contains("Cookie") || trimmed.contains("cookie") {
        return truncate_detail(trimmed, 120);
    }
    if trimmed.contains("token 接口未成功") || trimmed.contains("FAIL_SYS") {
        return "登录态异常，请重新扫码或完成滑块验证".to_string();
    }
    if trimmed.starts_with('{') || trimmed.contains("\"ret\"") {
        return "闲鱼接口返回异常，请稍后重试".to_string();
    }
    truncate_detail(trimmed, 120)
}

fn pct(success: u32, total: u32) -> u32 {
    success.saturating_mul(100).checked_div(total).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    struct MockStore {
        logs: Mutex<Vec<RiskLogItem>>,
        config: Mutex<RiskConfig>,
    }

    impl RiskStore for MockStore {
        fn list_logs(&self, owner_id: i64, query: &RiskLogQuery) -> DingDaResult<Vec<RiskLogItem>> {
            let logs = self.logs.lock().expect("lock");
            Ok(logs
                .iter()
                .filter(|log| {
                    log.owner_id == owner_id
                        && (query.account_id.is_empty() || log.account_id == query.account_id)
                        && (query.start_date.is_empty()
                            || log
                                .created_at
                                .as_deref()
                                .is_none_or(|t| t >= query.start_date.as_str()))
                        && (query.end_date.is_empty()
                            || log.created_at.as_deref().is_none_or(|t| {
                                t <= format!("{} 23:59:59", query.end_date).as_str()
                            }))
                        && (query.processing_status.is_empty()
                            || log.processing_status == query.processing_status)
                        && (query.call_type.is_empty()
                            || log.call_type.as_deref() == Some(query.call_type.as_str()))
                        && (query.call_user.is_empty()
                            || log
                                .call_user
                                .as_deref()
                                .is_some_and(|u| u.contains(&query.call_user)))
                })
                .cloned()
                .collect())
        }
        fn clear_logs(&self, owner_id: i64, account_id: &str) -> DingDaResult<()> {
            let mut logs = self.logs.lock().expect("lock");
            logs.retain(|log| {
                log.owner_id != owner_id || (!account_id.is_empty() && log.account_id != account_id)
            });
            Ok(())
        }
        fn clear_processing(&self, owner_id: i64) -> DingDaResult<()> {
            let mut logs = self.logs.lock().expect("lock");
            logs.retain(|log| log.owner_id != owner_id || log.processing_status != "processing");
            Ok(())
        }
        fn get_config(&self, owner_id: i64) -> DingDaResult<RiskConfig> {
            let _ = owner_id;
            Ok(self.config.lock().expect("lock").clone())
        }
        fn save_config(&self, owner_id: i64, config: &RiskConfig) -> DingDaResult<()> {
            let _ = owner_id;
            *self.config.lock().expect("lock") = config.clone();
            Ok(())
        }
        fn append_log(&self, mut log: RiskLogItem) -> DingDaResult<RiskLogItem> {
            if log.id == 0 {
                log.id = self
                    .logs
                    .lock()
                    .expect("lock")
                    .iter()
                    .map(|item| item.id)
                    .max()
                    .unwrap_or(0)
                    + 1;
            }
            self.logs.lock().expect("lock").push(log.clone());
            Ok(log)
        }

        fn update_log(&self, log: &RiskLogItem) -> DingDaResult<()> {
            let mut logs = self.logs.lock().expect("lock");
            if let Some(slot) = logs.iter_mut().find(|item| item.id == log.id) {
                *slot = log.clone();
                Ok(())
            } else {
                Err(format!("风控日志不存在: {}", log.id).into())
            }
        }
    }

    fn log(
        id: i64,
        account_id: &str,
        status: &str,
        call_type: &str,
        created_at: &str,
    ) -> RiskLogItem {
        RiskLogItem {
            id,
            owner_id: 1,
            account_id: account_id.to_string(),
            risk_type: "slider".to_string(),
            message: format!("事件 {id}"),
            processing_result: String::new(),
            processing_status: status.to_string(),
            captcha_engine: Some("playwright".to_string()),
            call_type: Some(call_type.to_string()),
            call_user: None,
            error_message: None,
            created_at: Some(created_at.to_string()),
            updated_at: None,
        }
    }

    fn store() -> MockStore {
        MockStore {
            logs: Mutex::new(vec![
                log(1, "acc-1", "success", "local", "2026-08-01 10:00:00"),
                log(2, "acc-1", "failed", "local", "2026-08-02 10:00:00"),
                log(3, "acc-2", "processing", "remote", "2026-08-03 10:00:00"),
            ]),
            config: Mutex::new(RiskConfig::default()),
        }
    }

    #[test]
    fn list_filters_and_paginates() {
        let mock = store();
        let service = RiskService::new(&mock);
        let query = RiskLogQuery {
            page: 1,
            page_size: 10,
            account_id: "acc-1".to_string(),
            ..Default::default()
        };
        let page = service.list(1, &query).expect("list");
        assert_eq!(page.total, 2);
        assert_eq!(page.data.len(), 2);
    }

    #[test]
    fn today_rate_three_dimensions() {
        let mock = store();
        let service = RiskService::new(&mock);
        let rate = service.today_success_rate(1, "2026-08-03").expect("rate");
        assert_eq!(rate.total, 1);
        assert_eq!(rate.remote_total, 1);
        assert_eq!(rate.processing, 1);
        assert_eq!(rate.remote_processing, 1);
    }

    #[test]
    fn clear_respects_scope() {
        let mock = store();
        let service = RiskService::new(&mock);
        service.clear(1, "acc-1").expect("clear");
        let remaining = mock.list_logs(1, &RiskLogQuery::default()).expect("list");
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].account_id, "acc-2");
        service.clear_processing(1).expect("clear processing");
        let remaining = mock.list_logs(1, &RiskLogQuery::default()).expect("list");
        assert!(remaining
            .iter()
            .all(|log| log.processing_status != "processing"));
    }

    #[test]
    fn config_rejects_token_api_domain() {
        let mock = store();
        let service = RiskService::new(&mock);
        let mut config = RiskConfig {
            remote_url: "https://api.xianyusite.shop/slider".to_string(),
            ..Default::default()
        };
        assert!(service.save_config(1, &config).is_err());
        config.remote_url = "https://your-host/slider".to_string();
        assert!(service.save_config(1, &config).is_ok());
    }

    #[test]
    fn record_im_risk_reuses_open_processing_log() {
        let mock = store();
        let service = RiskService::new(&mock);
        let first = service
            .record_im_risk(1, "acc-1", "闲鱼 IM", "punish captcha")
            .expect("first");
        let second = service
            .record_im_risk(1, "acc-1", "闲鱼 IM", "RGV587 again")
            .expect("second");
        assert_eq!(first.id, second.id);
        assert_eq!(second.processing_status, "processing");
        assert!(second.error_message.is_none());
        let processing = mock
            .list_logs(
                1,
                &RiskLogQuery {
                    account_id: "acc-1".to_string(),
                    processing_status: "processing".to_string(),
                    ..Default::default()
                },
            )
            .expect("list");
        assert_eq!(processing.len(), 1);
    }

    #[test]
    fn record_im_risk_does_not_store_raw_detail_in_error_message() {
        let mock = store();
        let service = RiskService::new(&mock);
        let detail = format!(
            "token 接口未成功: {{\"ret\":[\"FAIL_SYS_USER_VALIDATE\",\"RGV587_ERROR::SM::{}\"]]}}",
            "哎".repeat(520)
        );
        let log = service
            .record_im_risk(1, "acc-1", "闲鱼 IM", &detail)
            .expect("record");
        assert!(log.error_message.is_none());
    }

    #[test]
    fn record_slider_outcome_updates_processing() {
        let mock = store();
        let service = RiskService::new(&mock);
        service
            .record_im_risk(1, "acc-new", "闲鱼 IM", "punish captcha")
            .expect("processing");
        let ok = service
            .record_slider_outcome(1, "acc-new", true, "")
            .expect("success");
        assert_eq!(ok.processing_status, "success");
        assert!(ok.processing_result.contains("通过"));
        assert!(ok.error_message.is_none());
        let processing = service
            .list(
                1,
                &RiskLogQuery {
                    account_id: "acc-new".to_string(),
                    processing_status: "processing".to_string(),
                    ..Default::default()
                },
            )
            .expect("list");
        assert_eq!(processing.total, 0);

        service
            .record_im_risk(1, "acc-fail", "闲鱼 IM", "punish captcha")
            .expect("processing");
        let failed = service
            .record_slider_outcome(1, "acc-fail", false, "浏览器续期超时")
            .expect("failed");
        assert_eq!(failed.processing_status, "failed");
        assert!(failed.processing_result.contains("失败"));
        assert_eq!(failed.error_message.as_deref(), Some("浏览器续期超时"));
    }

    #[test]
    fn record_slider_outcome_updates_all_processing_for_account() {
        let mock = store();
        let service = RiskService::new(&mock);
        for _ in 0..3 {
            let mut log = log(0, "acc-multi", "processing", "local", "2026-08-04 10:00:00");
            log.id = 0;
            log.account_id = "acc-multi".to_string();
            mock.append_log(log).expect("append");
        }
        service
            .record_slider_outcome(1, "acc-multi", true, "")
            .expect("success");
        let remaining = mock
            .list_logs(
                1,
                &RiskLogQuery {
                    account_id: "acc-multi".to_string(),
                    processing_status: "processing".to_string(),
                    ..Default::default()
                },
            )
            .expect("list");
        assert!(remaining.is_empty());
    }
}
