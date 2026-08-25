//! 风控滑块 — Sidecar Playwright 续期 Cookie 并重连。
//!
//! 全局串行队列：同一时刻只跑一个浏览器续期（Camoufox 并发不稳定），
//! 其余账号排队，前一个结束后自动开跑。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-20

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::runtime::python::SidecarLifecycle;
use crate::runtime::tasks::{TaskKind, TaskManager};
use common::contracts::ChannelSidecarCookieRenewRequest;
use common::events::{emit, AppEvent, ChannelStatusEvent, EventSink};
use platform::domain::account::{AccountService, AccountStore, AccountUpdate};
use platform::domain::risk::RiskService;
use platform::shared::cookies::parse_credential;
use platform::shared::stores::InMemoryRiskStore;
use platform::xianyu::extract_punish_url;

use crate::platforms::xianyu::ipc::account_connection::to_channel_account;
use crate::shared::channel::dispatcher::ChannelDispatcher;

/// 与前端 `CHANNEL_CONNECTION_STATUS_MAP` 对齐的 UI 状态键。
pub mod ui_status {
    pub const RENEWING: &str = "renewing";
    pub const QUEUED: &str = "queued";
    pub const ERROR: &str = "error";
    pub const CONNECTING: &str = "connecting";
}

/// 调度续期的结果（供协调器决定推送哪条 UI 状态）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RenewSchedule {
    /// 已拉起浏览器续期任务（队列空闲，立即执行）。
    Started,
    /// 已有其它账号在跑，本账号已入队。
    Queued,
    /// 本账号已在跑或已在队列中。
    InFlight,
    /// 冷却窗口内，跳过本次拉起。
    Cooldown,
    /// 功能关闭或本机滑块禁用。
    Disabled,
}

/// 全局串行队列状态。
struct RenewQueue {
    /// 当前正在浏览器续期的账号。
    running: Option<String>,
    /// 等待续期的 (account_id, risk_detail)。
    pending: VecDeque<(String, String)>,
}

impl RenewQueue {
    fn new() -> Self {
        Self {
            running: None,
            pending: VecDeque::new(),
        }
    }

    fn contains_account(&self, account_id: &str) -> bool {
        self.running.as_deref() == Some(account_id)
            || self.pending.iter().any(|(id, _)| id == account_id)
    }
}

/// 浏览器续期编排 — 全局串行队列、写回 Cookie、重连渠道。
///
/// 每次续期运行经 Runtime `TaskManager` 创建并执行，复用任务生命周期观测与关闭取消。
pub struct RiskCookieRenewer {
    sidecar: Arc<SidecarLifecycle>,
    account_store: Arc<dyn AccountStore>,
    dispatcher: Arc<ChannelDispatcher>,
    risk_store: Option<Arc<InMemoryRiskStore>>,
    sink: Arc<dyn EventSink>,
    owner_id: i64,
    manager: Arc<TaskManager>,
    queue: Mutex<RenewQueue>,
    last_attempt_ms: Mutex<std::collections::HashMap<String, u128>>,
}

impl RiskCookieRenewer {
    /// 创建续期编排器。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    pub fn new(
        sidecar: Arc<SidecarLifecycle>,
        account_store: Arc<dyn AccountStore>,
        dispatcher: Arc<ChannelDispatcher>,
        risk_store: Option<Arc<InMemoryRiskStore>>,
        sink: Arc<dyn EventSink>,
        owner_id: i64,
        manager: Arc<TaskManager>,
    ) -> Self {
        Self {
            sidecar,
            account_store,
            dispatcher,
            risk_store,
            sink,
            owner_id,
            manager,
            queue: Mutex::new(RenewQueue::new()),
            last_attempt_ms: Mutex::new(std::collections::HashMap::new()),
        }
    }

    fn now_ms() -> u128 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or(0)
    }

    /// 是否在冷却中（只读；真正开跑后再 `mark_attempt`）。
    fn in_cooldown(&self, account_id: &str) -> bool {
        let now = Self::now_ms();
        let last = self
            .last_attempt_ms
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        last.get(account_id)
            .is_some_and(|prev| now.saturating_sub(*prev) < 60_000)
    }

    fn mark_attempt(&self, account_id: &str) {
        let mut last = self
            .last_attempt_ms
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        last.insert(account_id.to_string(), Self::now_ms());
    }

    fn clear_attempt(&self, account_id: &str) {
        let mut last = self
            .last_attempt_ms
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        last.remove(account_id);
    }

    fn local_slider_disabled(&self) -> bool {
        let Some(store) = &self.risk_store else {
            return false;
        };
        RiskService::new(store.as_ref())
            .get_config(self.owner_id)
            .map(|config| config.local_slider_disabled)
            .unwrap_or(false)
    }

    /// 向前端推送 canonical UI 状态（`state` 必须是 map 键，`detail` 仅短中文）。
    fn emit_ui_status(&self, account_id: &str, state: &str, detail: &str) {
        let event = AppEvent::ChannelStatus(ChannelStatusEvent {
            account_id: account_id.to_string(),
            state: state.to_string(),
            detail: Some(detail.to_string()),
        });
        if let Err(error) = emit(self.sink.as_ref(), &event) {
            warn!(%error, account = %account_id, "推送续期状态失败");
        }
    }

    /// 入队或立即开跑；返回调度结果。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-21
    pub fn spawn_renew(self: Arc<Self>, account_id: String, detail: String) -> RenewSchedule {
        if !common::constants::FeatureFlags::from_env().auto_cookie_renew {
            warn!(
                account = %account_id,
                "已关闭自动 Cookie 续期（DINGDA_DISABLE_AUTO_COOKIE_RENEW=1），跳过"
            );
            return RenewSchedule::Disabled;
        }
        if self.local_slider_disabled() {
            warn!(account = %account_id, "本机滑块处理已禁用，跳过浏览器续期");
            return RenewSchedule::Disabled;
        }
        if self.in_cooldown(&account_id) {
            warn!(account = %account_id, "续期冷却中，跳过重复拉起");
            return RenewSchedule::Cooldown;
        }

        let start_now = {
            let mut queue = self
                .queue
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if queue.contains_account(&account_id) {
                warn!(account = %account_id, "续期任务已在跑或排队中，跳过");
                return RenewSchedule::InFlight;
            }
            if queue.running.is_some() {
                let pending_len = queue.pending.len() + 1;
                queue
                    .pending
                    .push_back((account_id.clone(), detail.clone()));
                warn!(
                    account = %account_id,
                    queue_len = pending_len,
                    running = ?queue.running,
                    "续期已入队，等待前序账号完成"
                );
                drop(queue);
                self.emit_ui_status(&account_id, ui_status::QUEUED, "排队等待过滑块，请稍候");
                return RenewSchedule::Queued;
            }
            queue.running = Some(account_id.clone());
            true
        };

        if start_now {
            self.start_renew_job(account_id, detail);
            return RenewSchedule::Started;
        }
        RenewSchedule::InFlight
    }

    /// 真正拉起一次浏览器续期任务（调用方已占用 `queue.running`）。
    fn start_renew_job(self: Arc<Self>, account_id: String, detail: String) {
        self.mark_attempt(&account_id);

        let punish_preview = platform::xianyu::extract_punish_url(&detail)
            .map(|url| url.chars().take(80).collect::<String>())
            .unwrap_or_else(|| "(无 punish URL，Sidecar 将打开首页检测滑块)".into());
        warn!(
            account = %account_id,
            punish = %punish_preview,
            "风控触发，开始自动滑块续期"
        );

        self.emit_ui_status(&account_id, ui_status::RENEWING, "正在过滑块验证，请稍候");

        let run_id = self.manager.create(TaskKind::Renew);
        let renewer = self.clone();
        let renew_account = account_id.clone();
        let future = async move {
            if let Err(error) = renewer.dispatcher.disconnect(&renew_account).await {
                warn!(account = %renew_account, %error, "续期前断开连接失败（继续尝试浏览器续期）");
            }
            renewer.emit_ui_status(
                &renew_account,
                ui_status::RENEWING,
                "正在过滑块验证，请稍候",
            );
            let result = renewer.renew_once(&renew_account, &detail).await;
            match &result {
                Ok(()) => {
                    info!(account = %renew_account, "滑块续期完成，已重连");
                    renewer.record_slider_log(&renew_account, true, "");
                }
                Err(error) => {
                    warn!(account = %renew_account, %error, "滑块续期失败");
                    renewer.clear_attempt(&renew_account);
                    renewer.record_slider_log(&renew_account, false, error);
                    let short = error.chars().take(80).collect::<String>();
                    renewer.emit_ui_status(
                        &renew_account,
                        ui_status::ERROR,
                        &format!("滑块续期失败：{short}"),
                    );
                }
            }
            renewer.finish_and_pump_queue(&renew_account);
            result.map(|_| ())
        };
        if let Err(error) = self.manager.start(run_id, future) {
            warn!(%error, account = %account_id, "续期任务启动失败");
        }
    }

    /// 把过滑块结果写入风控日志（成功 / 失败）。
    fn record_slider_log(&self, account_id: &str, success: bool, detail: &str) {
        let Some(store) = &self.risk_store else {
            return;
        };
        let service = RiskService::new(store.as_ref());
        match service.record_slider_outcome(self.owner_id, account_id, success, detail) {
            Ok(log) => {
                info!(
                    account = %account_id,
                    log_id = log.id,
                    success,
                    "已写入过滑块风控日志"
                );
            }
            Err(error) => {
                warn!(account = %account_id, %error, "写入过滑块风控日志失败");
            }
        }
    }

    /// 当前任务结束：清 running，弹出队首继续跑。
    fn finish_and_pump_queue(self: &Arc<Self>, finished_account_id: &str) {
        let next = {
            let mut queue = self
                .queue
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            if queue.running.as_deref() == Some(finished_account_id) {
                queue.running = None;
            }
            let next = queue.pending.pop_front();
            if let Some((ref next_id, _)) = next {
                queue.running = Some(next_id.clone());
            }
            let remain = queue.pending.len();
            if let Some((ref next_id, _)) = next {
                info!(
                    finished = %finished_account_id,
                    next = %next_id,
                    remain,
                    "续期队列推进"
                );
            } else {
                info!(finished = %finished_account_id, "续期队列已空");
            }
            next
        };

        if let Some((next_id, next_detail)) = next {
            // 队首开跑前再推一次，把 queued → renewing。
            self.clone().start_renew_job(next_id, next_detail);
        }
    }

    /// 执行一次浏览器续期并重连。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    pub async fn renew_once(&self, account_id: &str, detail: &str) -> Result<(), String> {
        if self.local_slider_disabled() {
            return Err("本机滑块处理已禁用".into());
        }

        let account = self
            .account_store
            .get_account(self.owner_id, account_id)
            .map_err(|error| error.to_string())?
            .ok_or_else(|| format!("账号不存在: {account_id}"))?;
        if !account.has_cookie() {
            return Err("账号缺少 Cookie".into());
        }

        let cookies = parse_credential(&account.cookie);
        if cookies.is_empty() {
            return Err("Cookie 解析失败".into());
        }

        if let Err(error) = self.sidecar.ensure_running().await {
            return Err(format!("Sidecar 未就绪: {error}"));
        }

        let punish_url = extract_punish_url(detail);
        warn!(
            account = %account_id,
            has_punish_url = punish_url.is_some(),
            "正在打开浏览器完成滑块验证"
        );
        self.emit_ui_status(
            account_id,
            ui_status::RENEWING,
            "正在打开浏览器完成滑块验证",
        );

        let request = ChannelSidecarCookieRenewRequest {
            account_id: account_id.to_string(),
            cookies,
            punish_url,
            trace_id: Some(format!("renew-{account_id}")),
        };
        let response = crate::runtime::python::routes::channel_cookie_renew::call(
            self.sidecar.client(),
            request,
        )
        .await
        .map_err(|error| error.to_string())?;

        if !response.ok {
            return Err(response.detail.unwrap_or_else(|| "浏览器续期失败".into()));
        }

        let renewed = response
            .cookies
            .ok_or_else(|| "续期未返回 Cookie".to_string())?;
        let credential = serde_json::to_string(&renewed).map_err(|error| error.to_string())?;

        let service = AccountService::new(self.account_store.as_ref());
        let updated = service
            .update(
                self.owner_id,
                account_id,
                &AccountUpdate {
                    cookie: Some(credential),
                    ..Default::default()
                },
            )
            .map_err(|error| error.to_string())?;

        self.emit_ui_status(account_id, ui_status::CONNECTING, "滑块通过，正在重连");

        let _ = self.dispatcher.disconnect(account_id).await;
        let channel_account = to_channel_account(self.owner_id, &updated);
        self.dispatcher
            .connect(&channel_account)
            .await
            .map_err(|error| error.to_string())?;

        Ok(())
    }
}
