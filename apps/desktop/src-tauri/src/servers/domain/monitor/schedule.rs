//! 监控定时调度 — 下次运行时间、暂停/恢复（冻结剩余倒计时）。

use chrono::{DateTime, Duration, Utc};

use super::MonitorTask;

/// 距离下次定时运行的剩余秒数（暂停时读冻结值）。
pub fn schedule_remaining_secs(task: &MonitorTask, now: DateTime<Utc>) -> u64 {
    if task.schedule_paused {
        return task.schedule_remaining_secs.unwrap_or(0);
    }
    if let Some(next) = task.next_run_at.as_deref() {
        if let Ok(parsed) = DateTime::parse_from_rfc3339(next) {
            return (parsed.with_timezone(&Utc) - now).num_seconds().max(0) as u64;
        }
    }
    if let Some(last) = task.last_run_at.as_deref() {
        if let Ok(parsed) = DateTime::parse_from_rfc3339(last) {
            let next =
                parsed.with_timezone(&Utc) + Duration::minutes(task.interval_minutes.max(1) as i64);
            return (next - now).num_seconds().max(0) as u64;
        }
    }
    0
}

/// 是否已到点执行定时任务。
pub fn is_schedule_due(task: &MonitorTask, now: DateTime<Utc>) -> bool {
    if !task.enabled || task.schedule_paused || task.is_running {
        return false;
    }
    schedule_remaining_secs(task, now) == 0
}

/// 手动「立即运行」：重置为完整间隔并暂停定时（运行结束后仍暂停，需用户恢复）。
pub fn reset_and_pause_schedule_for_manual_run(task: &mut MonitorTask, now: DateTime<Utc>) {
    if !task.enabled {
        return;
    }
    let full_secs = task.interval_minutes.max(1) as u64 * 60;
    task.schedule_paused = true;
    task.schedule_remaining_secs = Some(full_secs);
    task.next_run_at = None;
    task.updated_at = now.to_rfc3339();
}

/// 一次运行结束后推进下次运行时间（仅定时调度且未暂停时）。
pub fn bump_next_run_after_run(task: &mut MonitorTask, now: DateTime<Utc>) {
    if !task.enabled || task.schedule_paused {
        return;
    }
    let mins = task.interval_minutes.max(1) as i64;
    task.next_run_at = Some((now + Duration::minutes(mins)).to_rfc3339());
    task.schedule_remaining_secs = None;
}

/// 暂停定时 — 冻结当前剩余秒数（类似 React 挂起更新）。
pub fn pause_schedule(task: &mut MonitorTask, now: DateTime<Utc>) {
    if !task.enabled || task.schedule_paused {
        return;
    }
    task.schedule_remaining_secs = Some(schedule_remaining_secs(task, now));
    task.schedule_paused = true;
    task.next_run_at = None;
    task.updated_at = now.to_rfc3339();
}

/// 恢复定时 — 从冻结的剩余秒数继续倒计时。
pub fn resume_schedule(task: &mut MonitorTask, now: DateTime<Utc>) {
    if !task.enabled || !task.schedule_paused {
        return;
    }
    let remaining = task
        .schedule_remaining_secs
        .unwrap_or_else(|| task.interval_minutes.max(1) as u64 * 60);
    task.schedule_paused = false;
    task.schedule_remaining_secs = None;
    task.next_run_at = Some((now + Duration::seconds(remaining as i64)).to_rfc3339());
    task.updated_at = now.to_rfc3339();
}

/// 启用定时且未暂停时，确保存在 next_run_at。
pub fn ensure_next_run_on_enable(task: &mut MonitorTask, now: DateTime<Utc>) {
    if !task.enabled || task.schedule_paused || task.next_run_at.is_some() {
        return;
    }
    let remaining = schedule_remaining_secs(task, now);
    task.next_run_at = Some((now + Duration::seconds(remaining as i64)).to_rfc3339());
}
