//! 应用启动后后台账号探活（不阻塞 UI）。

use crate::application::account::{probe_all_accounts_on_startup, ACCOUNTS_SESSION_PROBED_TOPIC};
use crate::bootstrap::startup;
use crate::bootstrap::state::AppState;
use crate::commands::AccountHandle;
use crate::infrastructure::sidecar::agent_task::DEFAULT_OWNER_ID;
use tauri::{AppHandle, Emitter, Manager};

/// 在平台就绪后后台探活全部账号，完成后推送 `dingda/accounts-session-probed`。
pub fn spawn(app: &AppHandle) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        startup::phase("rust.account_probe.begin");

        let state = app.state::<AppState>();
        if let Err(error) = state.lifecycle.ensure_running().await {
            warn!(
                target: "dingda.lifecycle",
                %error,
                "启动账号探活：Sidecar 未就绪，跳过"
            );
            emit_empty(&app);
            startup::phase("rust.account_probe.skip");
            return;
        }

        let handle = app.state::<AccountHandle>();
        let payload = probe_all_accounts_on_startup(
            handle.store.clone(),
            state.lifecycle.clone(),
            DEFAULT_OWNER_ID,
        )
        .await;

        let count = payload.probes.len();
        let online = payload.probes.iter().filter(|item| item.online).count();
        if let Err(error) = app.emit(ACCOUNTS_SESSION_PROBED_TOPIC, &payload) {
            warn!(
                target: "dingda.lifecycle",
                %error,
                "启动账号探活事件推送失败"
            );
        }

        startup::phase_detail(
            "rust.account_probe.done",
            &format!("total={count} online={online}"),
        );
    });
}

fn emit_empty(app: &AppHandle) {
    use crate::application::account::AccountsSessionProbedPayload;
    let _ = app.emit(
        ACCOUNTS_SESSION_PROBED_TOPIC,
        AccountsSessionProbedPayload { probes: vec![] },
    );
}
