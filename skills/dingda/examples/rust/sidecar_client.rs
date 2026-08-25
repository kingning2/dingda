//! Example: Rust sidecar HTTP client (Rust → Python).
//!
//! Real code lives in `apps/desktop/src-tauri/src/runtime/python/client.rs`.
//! This file documents the pattern only.

/*
use crate::runtime::python::client::SidecarClient;
use crate::runtime::python::routes::agent_ping::call;

async fn example(runtime_port: u16) -> Result<(), Box<dyn std::error::Error>> {
    let client = SidecarClient::new(runtime_port);
    let response = call(&client).await?;
    assert!(response.ok);
    Ok(())
}
*/

fn main() {
    // documentation-only example; see apps/desktop/src-tauri/src/runtime/python/
}
