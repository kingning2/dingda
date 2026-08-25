//! 平台描述 Tauri commands — 把编译期注册表暴露给前端。

use crate::contracts::DingDaResult;
use crate::core::protocol::registry::PlatformRegistry;
use serde::Serialize;

use crate::cmd::IpcResponse;

/// 平台描述 IPC 返回体，字段与前端约定对齐。
#[derive(Debug, Clone, Serialize)]
pub struct PlatformDescriptorDto {
    pub kind: String,
    pub name: String,
    pub capabilities: Vec<String>,
}

/// 列出当前构建已编译进二进制的平台描述。
#[tauri::command]
pub fn platform_descriptors() -> DingDaResult<IpcResponse<Vec<PlatformDescriptorDto>>> {
    let registry = PlatformRegistry::new();
    let descriptors = registry
        .descriptors()
        .into_iter()
        .map(|descriptor| PlatformDescriptorDto {
            kind: descriptor.kind,
            name: descriptor.name,
            capabilities: descriptor.capabilities.as_strings(),
        })
        .collect();
    Ok(IpcResponse::ok(descriptors))
}
