mod channel_platform_cfg {
    include!("../../../tooling/build/channel_platform_cfg.rs");
}

use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    // sidecar 命名用目标 triple（与 bundled sidecar 命名一致）。
    let target = env::var("TARGET").unwrap_or_else(|_| "unknown".into());
    println!("cargo:rustc-env=DINGDA_TARGET_TRIPLE={target}");

    // license verifier 校验数据（原 infra build.rs）。
    let license_triple = license_target_triple(&target);
    println!("cargo:rustc-env=DINGDA_LICENSE_TARGET_TRIPLE={license_triple}");

    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap_or_default());
    let generated = manifest_dir.join("generated");
    println!(
        "cargo:rerun-if-changed={}",
        generated.join("license_verifier.sha256").display()
    );
    println!(
        "cargo:rerun-if-changed={}",
        generated.join("license_attest_key.hex").display()
    );
    let sha = read_trimmed(generated.join("license_verifier.sha256"));
    let attest = read_trimmed(generated.join("license_attest_key.hex"));
    println!("cargo:rustc-env=DINGDA_LICENSE_VERIFIER_SHA256={sha}");
    println!("cargo:rustc-env=DINGDA_LICENSE_ATTEST_KEY_HEX={attest}");

    channel_platform_cfg::emit_channel_platform_cfg(
        "../../../tooling/config/channel-platforms.json",
    );
    ensure_external_bin_stub_for_dev("sidecar");
    ensure_external_bin_stub_for_dev("license-verifier");
    tauri_build::build();
}

/// Windows 上固定映射为 `*-windows-msvc`，与 bundled verifier 命名一致。
fn license_target_triple(target: &str) -> String {
    if cfg!(target_os = "windows") || target.contains("windows") {
        if target.contains("windows-gnu") {
            return target.replace("windows-gnu", "windows-msvc");
        }
        if target.contains("windows-msvc") {
            return target.to_string();
        }
        return "x86_64-pc-windows-msvc".into();
    }
    target.to_string()
}

fn read_trimmed(path: PathBuf) -> String {
    fs::read_to_string(&path)
        .map(|value| value.trim().to_string())
        .unwrap_or_default()
}

/// Tauri validates `externalBin` at compile time. Release builds must run
/// the matching build script first; debug/clippy only needs a placeholder file.
fn ensure_external_bin_stub_for_dev(base_name: &str) {
    let profile = env::var("PROFILE").unwrap_or_else(|_| "debug".into());
    if profile == "release" {
        return;
    }

    let target = env::var("TARGET").unwrap_or_else(|_| "unknown".into());
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let binaries_dir = manifest_dir.join("binaries");
    let binary_path = binaries_dir.join(external_binary_name(base_name, &target));

    if binary_path.is_file() {
        println!("cargo:rerun-if-changed={}", binary_path.display());
        return;
    }

    if let Err(error) = fs::create_dir_all(&binaries_dir) {
        println!("cargo:warning=create binaries dir failed: {error}");
        return;
    }

    #[cfg(unix)]
    write_unix_stub(&binary_path);

    #[cfg(windows)]
    write_windows_stub(&binary_path);

    println!(
        "cargo:warning=created dev {base_name} stub at {}",
        binary_path.display()
    );
    println!("cargo:rerun-if-changed={}", binaries_dir.display());
}

fn external_binary_name(base_name: &str, target: &str) -> String {
    let base = format!("{base_name}-{target}");
    if target.contains("windows") {
        format!("{base}.exe")
    } else {
        base
    }
}

#[cfg(unix)]
fn write_unix_stub(path: &PathBuf) {
    use std::os::unix::fs::PermissionsExt;

    const STUB: &[u8] = b"#!/bin/sh\nexit 0\n";
    let write_result = fs::write(path, STUB).and_then(|_| {
        fs::metadata(path).and_then(|metadata| {
            let mut permissions = metadata.permissions();
            permissions.set_mode(0o755);
            fs::set_permissions(path, permissions)
        })
    });
    if let Err(error) = write_result {
        println!("cargo:warning=write externalBin stub failed: {error}");
    }
}

#[cfg(windows)]
fn write_windows_stub(path: &PathBuf) {
    if let Ok(system_root) = env::var("SystemRoot") {
        let donor = PathBuf::from(system_root)
            .join("System32")
            .join("where.exe");
        if donor.is_file() && fs::copy(donor, path).is_ok() {
            return;
        }
    }

    if fs::write(path, [0]).is_err() {
        println!("cargo:warning=write externalBin stub failed");
    }
}
