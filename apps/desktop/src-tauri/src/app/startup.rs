//! App 启动时钟：从 `lib.rs launch()` 起算，中文阶段日志含「本段耗时 / 累计」。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-24

use std::collections::HashSet;
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

static STARTED_AT: OnceLock<Instant> = OnceLock::new();
static LOGGED_PHASES: Mutex<Option<HashSet<String>>> = Mutex::new(None);
static LAST_AT_MS: Mutex<u128> = Mutex::new(0);

const STARTUP_TARGET: &str = "dingda.lifecycle";

/// 标记进程启动原点。应在 `init_tracing()` 之后立刻调用一次。
pub fn mark_start() {
    let _ = STARTED_AT.set(Instant::now());
    if let Ok(mut last) = LAST_AT_MS.lock() {
        *last = 0;
    }
}

/// 距进程启动原点的毫秒数；未标记时为 0。
pub fn elapsed_ms() -> u128 {
    STARTED_AT
        .get()
        .map(|started| started.elapsed().as_millis())
        .unwrap_or(0)
}

/// 记录一个启动阶段。日志正文固定以 `[启动]` 开头，便于检索。
///
/// # 参数
///
/// * `phase` — 阶段名，如 `rust.setup.done`
pub fn phase(phase: &str) {
    phase_detail(phase, "");
}

/// 记录阶段并附带短详情（窗口 label、URL 等）。
///
/// # 参数
///
/// * `phase` — 阶段名
/// * `detail` — 附加字段，已是 `k=v` 形式；空则省略
pub fn phase_detail(phase: &str, detail: &str) {
    let total = elapsed_ms();
    let delta = match LAST_AT_MS.lock() {
        Ok(mut last) => {
            let d = total.saturating_sub(*last);
            *last = total;
            d
        }
        Err(_) => 0,
    };
    let label = phase_label(phase);
    if detail.is_empty() {
        info!(
            target: STARTUP_TARGET,
            "[启动] {label} | 本段 {delta}ms | 累计 {total}ms"
        );
        return;
    }
    info!(
        target: STARTUP_TARGET,
        "[启动] {label} | 本段 {delta}ms | 累计 {total}ms | {detail}"
    );
}

/// 同名阶段只打一次（窗口 resize/focus、HMR 导航不会刷屏）。
pub fn phase_once(phase: &str) {
    phase_once_detail(phase, "");
}

/// [`phase_once`] 的带详情版本。
pub fn phase_once_detail(phase: &str, detail: &str) {
    if !remember_phase(phase) {
        return;
    }
    phase_detail(phase, detail);
}

fn remember_phase(phase: &str) -> bool {
    let Ok(mut guard) = LOGGED_PHASES.lock() else {
        return true;
    };
    let logged = guard.get_or_insert_with(HashSet::new);
    logged.insert(phase.to_string())
}

fn phase_label(phase: &str) -> String {
    let name = match phase {
        "rust.process.start" => "进程启动",
        "rust.state.ready" => "应用状态就绪",
        "rust.setup.begin" => "开始装配",
        "rust.setup.done" => "装配完成",
        "rust.plugin_env.ready" => "插件环境就绪",
        "rust.sidecar.ensure_running.begin" => "开始拉起侧车（后台）",
        "rust.sidecar.ensure_running.ok" => "侧车就绪（后台）",
        "rust.sidecar.ensure_running.fail" => "侧车启动失败（后台）",
        "rust.business.ready" => "业务模块就绪",
        "rust.channel_db.ready" => "渠道数据库就绪",
        "rust.platform.ready" => "渠道平台就绪",
        "license.status.begin" => "开始查询授权",
        "license.status.end" => "授权查询完成",
        "tauri.window.none" => "无可用窗口",
        "tauri.window.ready" => "窗口就绪",
        "tauri.window.resized" => "窗口尺寸变化",
        "tauri.window.focused" => "窗口获得焦点",
        "tauri.window.destroyed" => "窗口销毁",
        "tauri.webview.load.start" => "开始加载页面",
        "tauri.webview.load.finish" => "页面加载完成",
        "tauri.run.ready" => "事件循环就绪",
        "tauri.run.resumed" => "事件循环恢复",
        "tauri.run.exit_requested" => "请求退出",
        "tauri.run.exit" => "进程退出",
        other => return format!("未登记阶段({other})"),
    };
    name.to_string()
}
