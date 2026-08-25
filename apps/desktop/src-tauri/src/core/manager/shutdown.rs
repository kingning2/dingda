//! 关闭顺序策略 — 固定顺序：取消任务 → 停止 Agent → 停止 Python。

use std::time::Duration;

use tokio::time::timeout;

use crate::core::manager::agent::AgentRuntime;
use crate::core::manager::python::PythonRuntime;
use crate::core::manager::tasks::TaskManager;
use crate::core::manager::RUNTIME_TARGET;

/// 关闭策略。
pub struct ShutdownPolicy {
    /// 每步停止的超时上限。
    pub step_timeout: Duration,
}

impl Default for ShutdownPolicy {
    fn default() -> Self {
        Self {
            step_timeout: Duration::from_secs(5),
        }
    }
}

/// 执行有序关闭。
///
/// 幂等由 supervisor 的 `shutdown_started` 守卫保证；本函数只关心顺序与超时，
/// 覆盖重复关闭 / Python 已崩溃 / Task 已结束等场景（均为无操作或记录日志）。
pub async fn run_shutdown(
    policy: &ShutdownPolicy,
    tasks: &TaskManager,
    agent: &AgentRuntime,
    python: &PythonRuntime,
) {
    info!(target: RUNTIME_TARGET, "[runtime] shutdown.begin");

    tasks.cancel_all();
    agent.stop();

    match timeout(policy.step_timeout, python.stop()).await {
        Ok(Ok(())) => {}
        Ok(Err(error)) => error!(%error, "侧车关闭失败"),
        Err(_elapsed) => warn!(target: RUNTIME_TARGET, "[runtime] python.stop.timeout"),
    }

    info!(target: RUNTIME_TARGET, "[runtime] shutdown.done");
}
