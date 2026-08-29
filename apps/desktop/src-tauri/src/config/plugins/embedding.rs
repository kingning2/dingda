//! 本地文本嵌入（BAAI/bge-small-zh-v1.5）插件。

use super::plugin_install_dir;
use super::types::{BuiltinPlugin, PluginFetch};
use crate::contracts::PluginItem;
use std::path::{Path, PathBuf};

/// 插件稳定 id。
pub const ID: &str = "embedding";

/// 安装完成标记文件名。
pub const INSTALLED_MARKER: &str = ".installed";

/// 注册表条目。
pub const SPEC: BuiltinPlugin = BuiltinPlugin {
    id: ID,
    name: "文本向量模型",
    description:
        "本地中文嵌入模型 BAAI/bge-small-zh-v1.5（约 100MB，512 维），按需下载，离线推理。",
    fetch: PluginFetch::EmbeddingModel,
};

pub fn is_installed(plugins_dir: &Path) -> bool {
    cache_dir(plugins_dir).join(INSTALLED_MARKER).is_file()
}

pub fn cache_dir(plugins_dir: &Path) -> PathBuf {
    plugin_install_dir(plugins_dir, ID)
}

pub fn to_item(plugins_dir: &Path, error: Option<String>) -> PluginItem {
    let installed = is_installed(plugins_dir);
    let status = if error.is_some() {
        "failed"
    } else if installed {
        "installed"
    } else {
        "not_installed"
    };
    PluginItem {
        id: SPEC.id.to_string(),
        name: SPEC.name.to_string(),
        description: SPEC.description.to_string(),
        status: status.to_string(),
        error,
    }
}
