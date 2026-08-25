//! License gate adapters：无锁 stub、fail-closed、verifier 子进程。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

mod fail_closed;
mod host_security;
mod unlocked;
mod verifier;

pub use fail_closed::FailClosedLicenseGate;
pub use host_security::LicenseHostSecurity;
pub use unlocked::UnlockedLicenseGate;
pub use verifier::VerifierProcessLicense;
