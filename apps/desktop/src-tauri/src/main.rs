// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Arc;

use dingda_lib::core::ports::license::LicenseGate;

#[cfg(not(feature = "license-lock"))]
use dingda_lib::core::infra::license::UnlockedLicenseGate;
#[cfg(feature = "license-lock")]
use dingda_lib::core::infra::license::{FailClosedLicenseGate, VerifierProcessLicense};

/// 按 Cargo feature 构造 License 闸门（仅桌面 bin 入口负责，lib 不内置策略）。
fn build_license_gate() -> Arc<dyn LicenseGate> {
    #[cfg(feature = "license-lock")]
    {
        match VerifierProcessLicense::from_env() {
            Ok(gate) => Arc::new(gate),
            Err(error) => {
                eprintln!("已启用授权锁但校验器不可用: {error}");
                Arc::new(FailClosedLicenseGate::new(error.to_string()))
            }
        }
    }
    #[cfg(not(feature = "license-lock"))]
    {
        Arc::new(UnlockedLicenseGate::new())
    }
}

fn main() {
    if let Err(error) = dingda_lib::run_with(build_license_gate()) {
        eprintln!("error while running tauri application: {error}");
        std::process::exit(1);
    }
}
