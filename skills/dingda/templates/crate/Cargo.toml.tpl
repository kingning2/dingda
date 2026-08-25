[package]
name = "{{FEATURE}}"
version.workspace = true
edition.workspace = true

[dependencies]
common = { path = "../common" }
ports = { path = "../ports" }
serde = { workspace = true }
thiserror = "2"
tracing = "0.1"
