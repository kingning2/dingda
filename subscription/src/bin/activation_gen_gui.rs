//! DingDa 激活码签发 GUI（Slint）。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use slint::ComponentHandle;
use subscription_activation::issue::{ActivationIssuer, IssueRequest};
use subscription_activation::machine_code::compute_machine_code;

slint::include_modules!();

/// 按套餐时长计算到期日期（本地时间），返回 YYYY-MM-DD。
fn compute_expiry_date(count: i64, unit_index: usize) -> Option<String> {
    if count <= 0 {
        return None;
    }
    use chrono::Datelike;
    let now = chrono::Local::now();
    let expiry = match unit_index {
        1 => add_months(now, count)?,
        2 => add_months(now, count.checked_mul(12)?)?,
        _ => now + chrono::Duration::days(count),
    };
    Some(format!(
        "{:04}-{:02}-{:02}",
        expiry.year(),
        expiry.month(),
        expiry.day()
    ))
}

/// 加 N 个自然月，月末溢出时收敛到该月最后一天。
fn add_months(
    now: chrono::DateTime<chrono::Local>,
    months: i64,
) -> Option<chrono::DateTime<chrono::Local>> {
    use chrono::{Datelike, TimeZone};
    let total = (now.year() as i64) * 12 + (now.month0() as i64) + months;
    let year = total.div_euclid(12);
    let month = total.rem_euclid(12) as u32 + 1;
    let last_day = days_in_month(year, month);
    let day = (now.day0() as i64).min(last_day as i64 - 1) as u32 + 1;
    let naive =
        chrono::NaiveDate::from_ymd_opt(year as i32, month, day)?.and_hms_opt(23, 59, 59)?;
    chrono::Local.from_local_datetime(&naive).single()
}

/// 某年某月的天数（month: 1-12）。
fn days_in_month(year: i64, month: u32) -> u32 {
    use chrono::Datelike;
    let (ny, nm) = if month == 12 {
        (year + 1, 1u32)
    } else {
        (year, month + 1)
    };
    chrono::NaiveDate::from_ymd_opt(ny as i32, nm, 1)
        .and_then(|d| d.pred_opt())
        .map(|d| d.day())
        .unwrap_or(28)
}

/// GUI 入口：打开签发窗口。
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 返回值
///
/// 窗口关闭后返回；平台错误向上传播。
/// 按当前套餐时长输入回显到期时间；输入无效时不动已有值。
fn update_expiry_from_duration(ui: &ActivationGenWindow) {
    let count = ui.get_duration_count_text().trim().parse::<i64>().ok();
    let unit = ui.get_duration_unit_index() as usize;
    if let Some(date) = count.and_then(|c| compute_expiry_date(c, unit)) {
        ui.set_expiry_date_text(date.into());
    }
}

fn main() -> Result<(), slint::PlatformError> {
    let window = ActivationGenWindow::new()?;
    let issuer = ActivationIssuer::new();

    {
        let ui = window.as_weak();
        window.on_fill_local_machine_code(move || {
            let Some(ui) = ui.upgrade() else {
                return;
            };
            match compute_machine_code() {
                Ok(code) => {
                    ui.set_machine_code(code.into());
                    ui.set_status_message("已填入本机设备码".into());
                }
                Err(error) => {
                    ui.set_status_message(format!("读取本机设备码失败: {error}").into());
                }
            }
        });
    }

    {
        let ui = window.as_weak();
        window.on_update_expiry(move || {
            let Some(ui) = ui.upgrade() else {
                return;
            };
            update_expiry_from_duration(&ui);
        });
    }

    // 启动时按默认套餐时长（30 天）回显一次到期时间。
    {
        let ui = window.as_weak();
        let _ = ui.upgrade_in_event_loop(|ui| update_expiry_from_duration(&ui));
    }

    {
        let ui = window.as_weak();
        window.on_generate_clicked(move || {
            let Some(ui) = ui.upgrade() else {
                return;
            };
            if ui.get_busy() {
                return;
            }
            ui.set_busy(true);
            ui.set_status_message("正在生成…".into());

            let expiry_text = ui.get_expiry_date_text().to_string();
            let expiry = match expiry_text.trim() {
                value if !value.is_empty() => Some(value.to_string()),
                _ => {
                    ui.set_busy(false);
                    ui.set_status_message("截止日期不能为空，格式：YYYY-MM-DD".into());
                    return;
                }
            };

            let request = IssueRequest {
                machine_code: ui.get_machine_code().to_string(),
                product: ui.get_product().to_string(),
                version: ui.get_version().to_string(),
                days: None,
                absolute_exp: expiry,
                private_key_path: {
                    let path = ui.get_private_key_path().to_string();
                    if path.trim().is_empty() {
                        None
                    } else {
                        Some(path)
                    }
                },
                output_path: ui.get_output_path().to_string(),
            };

            match issuer.issue(request) {
                Ok(result) => {
                    ui.set_token_preview(result.token.into());
                    ui.set_machine_code(result.machine_code.into());
                    ui.set_status_message(
                        format!(
                            "已生成: {}\n截止时间已编入激活码，与首次激活时间无关。",
                            result.output_path
                        )
                        .into(),
                    );
                }
                Err(error) => {
                    ui.set_status_message(format!("生成失败: {error}").into());
                }
            }
            ui.set_busy(false);
        });
    }

    window.run()
}
