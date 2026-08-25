//! Agent 生命周期状态机 — 仅状态；业务管理见 [`super::manager`]。

use std::sync::RwLock;

use super::state::AgentState;

/// Agent 生命周期状态机。
#[derive(Default)]
pub struct AgentLifecycle {
    state: RwLock<AgentState>,
}

impl AgentLifecycle {
    /// 当前状态。
    pub fn state(&self) -> AgentState {
        *self.state.read().expect("agent state lock")
    }

    /// 转移状态（幂等；仅记录状态，日志由调用方负责）。
    pub fn transition(&self, new: AgentState) {
        let previous = *self.state.read().expect("agent state lock");
        if previous != new {
            *self.state.write().expect("agent state lock") = new;
        }
    }
}
