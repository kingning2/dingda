//! Build script：混淆公钥、派生盐；可选编译 Slint UI。
//!
//! 作者：coisini
//! 创建时间：2026-07-16

use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let pem_path = manifest_dir.join("keys").join("public_key.pem");
    println!("cargo:rerun-if-changed={}", pem_path.display());
    println!("cargo:rerun-if-changed=ui/activation_gen.slint");

    let pem = fs::read_to_string(&pem_path).unwrap_or_else(|error| {
        panic!(
            "read public key failed at {}: {error}. Generate keys under subscription/keys/",
            pem_path.display()
        )
    });
    let pem_bytes = pem.as_bytes();

    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    write_obfuscated_public_key(&out_dir, pem_bytes);
    write_key_file_salt(&out_dir, pem_bytes);
    write_attestation_key(&out_dir, &manifest_dir, pem_bytes);

    #[cfg(feature = "gui")]
    {
        slint_build::compile("ui/activation_gen.slint").expect("compile activation_gen.slint");
    }
}

/// 将 PEM 拆成 XOR 混淆字节数组，供运行时还原。
fn write_obfuscated_public_key(out_dir: &PathBuf, pem_bytes: &[u8]) {
    let mask: u8 = 0xA5;
    let obfuscated: Vec<u8> = pem_bytes
        .iter()
        .enumerate()
        .map(|(index, byte)| byte ^ mask ^ ((index as u8).wrapping_mul(17)))
        .collect();

    let mut chunks = String::from("pub static OBFUSCATED_PUBLIC_KEY_CHUNKS: &[&[u8]] = &[\n");
    for chunk in obfuscated.chunks(48) {
        chunks.push_str("    &[");
        for (i, byte) in chunk.iter().enumerate() {
            if i > 0 {
                chunks.push_str(", ");
            }
            chunks.push_str(&format!("0x{byte:02X}"));
        }
        chunks.push_str("],\n");
    }
    chunks.push_str("];\n");
    chunks.push_str(&format!(
        "pub const PUBLIC_KEY_XOR_MASK: u8 = 0x{mask:02X};\n"
    ));
    chunks.push_str("pub const PUBLIC_KEY_INDEX_MUL: u8 = 17;\n");

    fs::write(out_dir.join("embedded_public_key.rs"), chunks)
        .expect("write embedded_public_key.rs");
}

/// 由公钥派生稳定的 `.key` 混淆盐（同公钥跨构建保持一致）。
fn write_key_file_salt(out_dir: &PathBuf, pem_bytes: &[u8]) {
    let digest = sha256_bytes(b"dingda.license.key.salt.v1", pem_bytes);
    let mut rust = String::from("pub static KEY_FILE_OBFUSCATION_SALT: &[u8] = &[");
    for (i, byte) in digest.iter().enumerate() {
        if i > 0 {
            rust.push_str(", ");
        }
        rust.push_str(&format!("0x{byte:02X}"));
    }
    rust.push_str("];\n");
    fs::write(out_dir.join("key_file_salt.rs"), rust).expect("write key_file_salt.rs");
}

/// 派生 attestation HMAC 密钥，并同步到 infra/generated 供主程序嵌入。
fn write_attestation_key(out_dir: &PathBuf, manifest_dir: &PathBuf, pem_bytes: &[u8]) {
    let digest = sha256_bytes(b"dingda.license.attest.v1", pem_bytes);
    let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();

    let mut rust = String::from("pub static ATTESTATION_KEY: &[u8] = &[");
    for (i, byte) in digest.iter().enumerate() {
        if i > 0 {
            rust.push_str(", ");
        }
        rust.push_str(&format!("0x{byte:02X}"));
    }
    rust.push_str("];\n");
    fs::write(out_dir.join("attestation_key.rs"), rust).expect("write attestation_key.rs");
    write_activation_code_key(out_dir, pem_bytes);

    let infra_generated = manifest_dir
        .join("..")
        .join("apps")
        .join("desktop")
        .join("src-tauri")
        .join("generated");
    let _ = fs::create_dir_all(&infra_generated);
    let attest_path = infra_generated.join("license_attest_key.hex");
    if let Err(error) = fs::write(&attest_path, format!("{hex}\n")) {
        // subscription 可能被单独检出；写失败不阻断 verifier 构建。
        eprintln!(
            "cargo:warning=could not write {}: {error}",
            attest_path.display()
        );
    }
}

/// 派生紧凑激活码 HMAC 密钥（verifier 与 activation-gen 共用）。
fn write_activation_code_key(out_dir: &PathBuf, pem_bytes: &[u8]) {
    let digest = sha256_bytes(b"dingda.license.compact.v1", pem_bytes);
    let mut rust = String::from("pub static ACTIVATION_CODE_KEY: &[u8] = &[");
    for (i, byte) in digest.iter().enumerate() {
        if i > 0 {
            rust.push_str(", ");
        }
        rust.push_str(&format!("0x{byte:02X}"));
    }
    rust.push_str("];\n");
    fs::write(out_dir.join("activation_code_key.rs"), rust).expect("write activation_code_key.rs");
}

/// 简化 SHA-256（避免 build.rs 拉依赖）：纯 Rust 最小实现不够，改用标准库不可用。
/// 使用手动 FIPS 风格会过长；此处用 `sha2` 需把 sha2 放进 build-dependencies。
fn sha256_bytes(domain: &[u8], payload: &[u8]) -> [u8; 32] {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(domain);
    hasher.update(payload);
    let result = hasher.finalize();
    let mut out = [0u8; 32];
    out.copy_from_slice(&result);
    out
}
