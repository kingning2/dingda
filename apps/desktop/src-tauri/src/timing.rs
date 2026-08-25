//! 通用异步耗时日志（配合 `#[timed]` 属性宏，需显式标注）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-13

use std::future::Future;
use std::time::Instant;

/// 执行异步 Future 并记录耗时（由显式 `#[timed]` 展开调用）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
///
/// # 参数
/// - `name` — 中文 command 名（日志字段 `command`）
/// - `fut` — 返回 `Result` 的异步逻辑
///
/// # 返回值
/// `fut` 的执行结果；同时输出完成/失败日志。
pub async fn timed_run<T, E, F>(name: &'static str, fut: F) -> Result<T, E>
where
    E: std::fmt::Display,
    F: Future<Output = Result<T, E>>,
{
    let timer = Timer::start(name);
    let result = fut.await;
    timer.finish(&result);
    result
}

/// 耗时计时器：完成时输出日志（通过显式 `#[timed]` 使用）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
pub struct Timer {
    name: &'static str,
    started: Instant,
}

impl Timer {
    /// 开始计时。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-13
    ///
    /// # 参数
    /// - `name` — 中文调用名
    ///
    /// # 返回值
    /// 计时器；调用 [`finish`](Self::finish) 输出日志。
    pub fn start(name: &'static str) -> Self {
        Self {
            name,
            started: Instant::now(),
        }
    }

    /// 按结果输出完成/失败日志。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-13
    ///
    /// # 参数
    /// - `result` — 执行结果
    pub fn finish<T, E: std::fmt::Display>(self, result: &Result<T, E>) {
        let duration_ms = self.started.elapsed().as_millis();
        match result {
            Ok(_) => {
                info!(command = self.name, duration_ms, "调用完成");
            }
            Err(error) => {
                warn!(
                    command = self.name,
                    duration_ms,
                    error = %error,
                    "调用失败"
                );
            }
        }
    }
}
