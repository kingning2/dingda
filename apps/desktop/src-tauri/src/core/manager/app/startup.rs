//! App 启动时钟：从 `lib.rs launch()` 起算 elapsed_ms，统一打 `[startup]` 阶段日志。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-24

use std::collections::HashSet;
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

static STARTED_AT: OnceLock<Instant> = OnceLock::new();
static LOGGED_PHASES: Mutex<Option<HashSet<String>>> = Mutex::new(None);

const STARTUP_TARGET: &str = "dingda.lifecycle";

/// 标记进程启动原点。应在 `init_tracing()` 之后立刻调用一次。
pub fn mark_start() {
    let _ = STARTED_AT.set(Instant::now());
}

/// 距进程启动原点的毫秒数；未标记时为 0。
pub fn elapsed_ms() -> u128 {
    STARTED_AT
        .get()
        .map(|started| started.elapsed().as_millis())
        .unwrap_or(0)
}

/// 记录一个启动阶段。日志正文固定以 `[startup]` 开头，便于检索。
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
    if detail.is_empty() {
        info!(
            target: STARTUP_TARGET,
            "[startup] phase={} elapsed_ms={}",
            phase,
            elapsed_ms()
        );
        return;
    }
    info!(
        target: STARTUP_TARGET,
        "[startup] phase={} elapsed_ms={} {}",
        phase,
        elapsed_ms(),
        detail
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
