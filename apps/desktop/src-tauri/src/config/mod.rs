//! 应用级配置存储 — AI 账号与内置插件（OCR、Camoufox 等）。
//!
//! 设置弹窗是应用级入口：AI 配置写入 `ai-config.json`；插件文件落在
//! `{app_local_data}/plugins/{plugin_id}/`（OCR 为 `plugins/ocr/tessdata/`，
//! Camoufox 为 `plugins/camoufox/`）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19
//! 更新：2026-08-21 — 增加 Camoufox 插件导出。

mod ai;
mod plugins;

use crate::contracts::contracts::{
    AiIpcConfigRequest, AiIpcConfigResponse, PluginIpcListResponse, PluginItem,
};
use crate::contracts::DingDaResult;
use std::path::{Path, PathBuf};

pub use ai::AiConfigStore;
pub use plugins::{
    embedding_cache_dir, embedding_installed, embedding_item, find_builtin,
    find_camoufox_executable, plugin_assets, plugin_install_dir, tmp_path, BuiltinPlugin,
    PluginAsset, PluginFetch, PluginVerify, BUILTIN_PLUGINS, PLUGIN_ID_CAMOUFOX,
    PLUGIN_ID_EMBEDDING, PLUGIN_ID_OCR,
};

/// 应用配置存储（AI JSON + 插件目录）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub struct ConfigStore {
    ai: AiConfigStore,
    data_dir: PathBuf,
    plugins_dir: PathBuf,
}

impl ConfigStore {
    /// 以配置目录与应用本地数据目录创建存储。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 参数
    ///
    /// * `config_dir` — 应用配置目录（AI JSON）
    /// * `data_dir` — 应用本地数据目录（插件根为 `{data_dir}/plugins`）
    ///
    /// # 返回值
    ///
    /// 新建的配置存储。
    pub fn new(config_dir: PathBuf, data_dir: PathBuf) -> Self {
        let plugins_dir = data_dir.join("plugins");
        Self {
            ai: AiConfigStore::new(config_dir),
            data_dir,
            plugins_dir,
        }
    }

    /// 读取 AI 配置；文件不存在时返回空配置。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 返回值
    ///
    /// AI 配置，或错误描述。
    pub async fn ai_get(&self) -> DingDaResult<AiIpcConfigResponse> {
        self.ai.get().await
    }

    /// 整体写入 AI 配置。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 参数
    ///
    /// * `config` — 待写入的完整 AI 配置
    ///
    /// # 返回值
    ///
    /// 持久化后的配置，或错误描述。
    pub async fn ai_set(&self, config: AiIpcConfigRequest) -> DingDaResult<AiIpcConfigResponse> {
        self.ai.set(config).await
    }

    /// 插件根目录 `{data_dir}/plugins`。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 返回值
    ///
    /// 本应用插件根路径。
    pub fn plugins_dir(&self) -> &Path {
        &self.plugins_dir
    }

    /// 指定插件的资源落盘目录。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 参数
    ///
    /// * `plugin_id` — 插件 id
    ///
    /// # 返回值
    ///
    /// 该插件在本应用目录下的安装路径。
    pub fn plugin_install_dir(&self, plugin_id: &str) -> PathBuf {
        plugins::plugin_install_dir(&self.plugins_dir, plugin_id)
    }

    /// 旧版 OCR 目录 `{data_dir}/tessdata`（只读兼容 / 卸载清理）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 返回值
    ///
    /// 旧版 tessdata 路径。
    pub fn legacy_ocr_dir(&self) -> PathBuf {
        self.data_dir.join("tessdata")
    }

    /// 列出内置插件及安装状态。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 返回值
    ///
    /// 插件列表。
    pub fn plugin_list(&self) -> PluginIpcListResponse {
        plugins::list_plugins(&self.plugins_dir, &self.legacy_ocr_dir())
    }

    /// 卸载插件：删除 `{plugins}/{plugin_id}/` 整目录；OCR 另清旧 tessdata。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    ///
    /// # 参数
    ///
    /// * `plugin_id` — 插件 id
    ///
    /// # 返回值
    ///
    /// 卸载后的插件条目。
    pub fn plugin_uninstall(&self, plugin_id: &str) -> DingDaResult<PluginItem> {
        plugins::uninstall_plugin(&self.plugins_dir, &self.legacy_ocr_dir(), plugin_id)
    }
}
