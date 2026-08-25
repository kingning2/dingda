//! 任务取消 — 轻量取消令牌与注册表。
//!
//! 基于 `tokio::sync::Notify` 实现（项目 Tokio 已具备），不引入额外依赖；
//! 幂等取消，可安全并发调用。

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use super::task::TaskId;

/// 轻量取消令牌。
#[derive(Clone, Default)]
pub struct CancellationToken {
    inner: Arc<Inner>,
}

#[derive(Default)]
struct Inner {
    cancelled: RwLock<bool>,
    notify: tokio::sync::Notify,
}

impl CancellationToken {
    /// 新建令牌（未取消）。
    pub fn new() -> Self {
        Self::default()
    }

    /// 是否已取消。
    pub fn is_cancelled(&self) -> bool {
        *self.inner.cancelled.read().expect("cancel flag lock")
    }

    /// 取消（幂等；仅首次会唤醒等待者）。
    pub fn cancel(&self) {
        let first = {
            let mut flag = self.inner.cancelled.write().expect("cancel flag lock");
            let was = *flag;
            *flag = true;
            !was
        };
        if first {
            self.inner.notify.notify_waiters();
        }
    }

    /// 等待取消（已取消则立即返回）。
    pub async fn cancelled(&self) {
        loop {
            if self.is_cancelled() {
                return;
            }
            let notified = self.inner.notify.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            if self.is_cancelled() {
                return;
            }
            notified.await;
        }
    }
}

/// 任务取消注册表。
#[derive(Default)]
pub struct TaskCancellation {
    tokens: RwLock<HashMap<TaskId, CancellationToken>>,
}

impl TaskCancellation {
    /// 注册任务并返回其取消令牌。
    pub fn register(&self, task_id: TaskId) -> CancellationToken {
        let token = CancellationToken::new();
        self.tokens
            .write()
            .expect("cancellation registry lock")
            .insert(task_id, token.clone());
        token
    }

    /// 取消单个任务。
    pub fn cancel(&self, task_id: &TaskId) {
        if let Some(token) = self
            .tokens
            .read()
            .expect("cancellation registry lock")
            .get(task_id)
        {
            token.cancel();
        }
    }

    /// 取消全部任务并清空注册表。
    pub fn cancel_all(&self) {
        let tokens: Vec<CancellationToken> = self
            .tokens
            .read()
            .expect("cancellation registry lock")
            .values()
            .cloned()
            .collect();
        for token in tokens {
            token.cancel();
        }
        self.tokens
            .write()
            .expect("cancellation registry lock")
            .clear();
    }

    /// 注销任务（执行结束后清理）。
    pub fn unregister(&self, task_id: &TaskId) {
        self.tokens
            .write()
            .expect("cancellation registry lock")
            .remove(task_id);
    }
}

#[cfg(test)]
mod tests {
    use super::TaskCancellation;

    #[test]
    fn cancel_all_is_noop_when_empty() {
        let cancellation = TaskCancellation::default();
        cancellation.cancel_all();
    }

    #[test]
    fn register_then_cancel_marks_token() {
        let cancellation = TaskCancellation::default();
        let token = cancellation.register("t-1".to_string());
        assert!(!token.is_cancelled());
        cancellation.cancel(&"t-1".to_string());
        assert!(token.is_cancelled());
    }
}
