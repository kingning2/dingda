//! AI 配置 JSON 文件读写。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-11

use crate::contracts::DingDaResult;
use crate::contracts::{AiIpcConfigRequest, AiIpcConfigResponse};
use std::io;
use std::path::PathBuf;
use tokio::sync::Mutex;

/// AI 平台与账号配置存储。
///
/// 配置持久化到 `app_config_dir/ai-config.json`；内部互斥锁串行化读写。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-11
pub struct AiConfigStore {
    path: PathBuf,
    lock: Mutex<()>,
}

impl AiConfigStore {
    /// 以指定配置目录创建存储（文件为 `config_dir/ai-config.json`）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-11
    ///
    /// # 参数
    ///
    /// * `config_dir` — 应用配置目录路径
    ///
    /// # 返回值
    ///
    /// 新建的存储实例。
    pub fn new(config_dir: PathBuf) -> Self {
        Self {
            path: config_dir.join("ai-config.json"),
            lock: Mutex::new(()),
        }
    }

    /// 读取当前配置；文件不存在时返回空配置。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-11
    ///
    /// # 返回值
    ///
    /// 配置内容，或错误描述。
    pub async fn get(&self) -> DingDaResult<AiIpcConfigResponse> {
        let _guard = self.lock.lock().await;
        match std::fs::read(&self.path) {
            Ok(bytes) => Ok(serde_json::from_slice::<AiIpcConfigResponse>(&bytes)
                .map_err(|error| format!("ai config parse failed: {error}"))?),
            Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(AiIpcConfigResponse {
                providers: Vec::new(),
                accounts: Vec::new(),
                graph_models: None,
            }),
            Err(error) => Err(format!("ai config read failed: {error}").into()),
        }
    }

    /// 整体写入配置，返回持久化后的结果。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-11
    ///
    /// # 参数
    ///
    /// * `config` — 待写入的完整配置
    ///
    /// # 返回值
    ///
    /// 持久化后的配置，或错误描述。
    pub async fn set(&self, config: AiIpcConfigRequest) -> DingDaResult<AiIpcConfigResponse> {
        let _guard = self.lock.lock().await;
        let response = AiIpcConfigResponse {
            providers: config.providers,
            accounts: config.accounts,
            graph_models: config.graph_models,
        };
        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| format!("ai config dir create failed: {error}"))?;
        }
        let bytes = serde_json::to_vec_pretty(&response)
            .map_err(|error| format!("ai config serialize failed: {error}"))?;
        std::fs::write(&self.path, bytes)
            .map_err(|error| format!("ai config write failed: {error}"))?;
        Ok(response)
    }
}
