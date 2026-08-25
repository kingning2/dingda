//! 插件下载协调 — 检测安装状态，并在用户触发时下载。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19

use crate::contracts::contracts::{PluginEventProgress, PluginItem};
use crate::contracts::DingDaResult;
use futures_util::StreamExt;
use std::collections::HashSet;
use std::io::Write;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter};
use tokio::sync::Mutex;

/// 进度事件最短间隔，避免每个 chunk 都刷前端。
const PROGRESS_EMIT_INTERVAL: Duration = Duration::from_millis(120);

use crate::config::{
    find_camoufox_executable, plugin_assets, tmp_path, ConfigStore, PLUGIN_ID_CAMOUFOX,
};

/// 插件下载进度事件 topic（与前端 `PLUGIN_PROGRESS_EVENT` 对齐；Tauri 禁止 `.`）。
pub const PLUGIN_PROGRESS_TOPIC: &str = "plugin/progress";

/// 跟踪进行中的插件下载，防止重复并发安装。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub struct PluginDownloadTracker {
    in_progress: Mutex<HashSet<String>>,
}

impl PluginDownloadTracker {
    /// 创建空的下载跟踪器。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    pub fn new() -> Self {
        Self {
            in_progress: Mutex::new(HashSet::new()),
        }
    }

    /// 标记插件开始下载；若已在下载中返回 `false`。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    pub async fn try_start(&self, plugin_id: &str) -> bool {
        self.in_progress.lock().await.insert(plugin_id.to_string())
    }

    /// 标记插件下载结束。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    pub async fn finish(&self, plugin_id: &str) {
        self.in_progress.lock().await.remove(plugin_id);
    }

    /// 插件是否正在下载。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-19
    pub async fn is_downloading(&self, plugin_id: &str) -> bool {
        self.in_progress.lock().await.contains(plugin_id)
    }
}

impl Default for PluginDownloadTracker {
    fn default() -> Self {
        Self::new()
    }
}

/// 列出插件并合并进行中的下载状态。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub async fn plugin_list_with_status(
    store: &ConfigStore,
    tracker: &PluginDownloadTracker,
) -> Vec<PluginItem> {
    let mut items = store.plugin_list().items;
    for item in &mut items {
        if tracker.is_downloading(&item.id).await {
            item.status = "downloading".to_string();
            item.error = None;
        }
    }
    items
}

/// 下载并安装指定插件（幂等；并发调用会跳过已在进行的任务）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
pub async fn install_plugin(
    app: &AppHandle,
    store: &ConfigStore,
    tracker: &PluginDownloadTracker,
    plugin_id: &str,
) -> DingDaResult<PluginItem> {
    let plugin_id = plugin_id.trim();
    if !tracker.try_start(plugin_id).await {
        info!(%plugin_id, "插件已在下载中，跳过重复任务");
        return Ok(plugin_item(store, tracker, plugin_id).await);
    }

    info!(%plugin_id, "开始安装插件");
    let result = install_plugin_inner(app, store, plugin_id).await;
    tracker.finish(plugin_id).await;

    match result {
        Ok(()) => {
            info!(%plugin_id, "插件安装完成");
            Ok(plugin_item(store, tracker, plugin_id).await)
        }
        Err(error) => {
            warn!(%error, %plugin_id, "插件安装失败");
            Ok(failed_plugin_item(store, plugin_id, error.to_string()))
        }
    }
}

async fn plugin_item(
    store: &ConfigStore,
    tracker: &PluginDownloadTracker,
    plugin_id: &str,
) -> PluginItem {
    plugin_list_with_status(store, tracker)
        .await
        .into_iter()
        .find(|item| item.id == plugin_id)
        .unwrap_or_else(|| failed_plugin_item(store, plugin_id, "插件状态不可用".to_string()))
}

fn failed_plugin_item(store: &ConfigStore, plugin_id: &str, message: String) -> PluginItem {
    store
        .plugin_list()
        .items
        .into_iter()
        .find(|item| item.id == plugin_id)
        .map(|mut item| {
            item.status = "failed".to_string();
            item.error = Some(message);
            item
        })
        .unwrap_or_else(|| crate::contracts::contracts::PluginItem {
            id: plugin_id.to_string(),
            name: plugin_id.to_string(),
            description: String::new(),
            status: "failed".to_string(),
            error: Some("插件不存在".to_string()),
        })
}

async fn install_plugin_inner(
    app: &AppHandle,
    store: &ConfigStore,
    plugin_id: &str,
) -> DingDaResult<()> {
    if plugin_id == PLUGIN_ID_CAMOUFOX && find_camoufox_executable(store.plugins_dir()).is_some() {
        info!(%plugin_id, "Camoufox 已安装，跳过下载");
        return Ok(());
    }

    let assets = plugin_assets(plugin_id)?;
    let install_dir = store.plugin_install_dir(plugin_id);
    info!(
        %plugin_id,
        path = %install_dir.display(),
        asset_count = assets.len(),
        "准备下载插件资源"
    );
    std::fs::create_dir_all(&install_dir).map_err(|error| {
        format!(
            "创建插件目录失败 path={} reason={error}；请检查本地数据目录权限后重试",
            install_dir.display()
        )
    })?;

    // Camoufox zip ~500MB，放宽超时。
    let timeout_secs = if plugin_id == PLUGIN_ID_CAMOUFOX {
        1800
    } else {
        300
    };
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(timeout_secs))
        .build()
        .map_err(|error| format!("创建下载客户端失败 reason={error}；请检查本机 TLS 配置后重试"))?;

    for asset in assets {
        download_asset(
            &client,
            app,
            plugin_id,
            &install_dir,
            asset.file_name,
            asset.url,
            asset.extract_zip,
        )
        .await?;
    }

    if plugin_id == PLUGIN_ID_CAMOUFOX {
        let exe = find_camoufox_executable(store.plugins_dir()).ok_or_else(|| {
            format!(
                "Camoufox 解压后未找到可执行文件 path={}；请卸载后重试下载",
                install_dir.display()
            )
        })?;
        info!(path = %exe.display(), "Camoufox 可执行文件已就绪");
        sync_camoufox_env(store);
    }
    Ok(())
}

/// 把当前 Camoufox / 插件目录写入进程环境，供 sidecar 继承。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-21
///
/// # 参数
/// - `store` — 配置存储
pub fn sync_camoufox_env(store: &ConfigStore) {
    let plugins = store.plugins_dir();
    std::env::set_var("DINGDA_PLUGINS_DIR", plugins.as_os_str());
    match find_camoufox_executable(plugins) {
        Some(exe) => {
            std::env::set_var("DINGDA_CAMOUFOX_EXE", exe.as_os_str());
            info!(path = %exe.display(), "已设置 DINGDA_CAMOUFOX_EXE");
        }
        None => {
            std::env::remove_var("DINGDA_CAMOUFOX_EXE");
        }
    }
}

async fn download_asset(
    client: &reqwest::Client,
    app: &AppHandle,
    plugin_id: &str,
    install_dir: &std::path::Path,
    file_name: &str,
    url: &str,
    extract_zip: bool,
) -> DingDaResult<()> {
    let dest = install_dir.join(file_name);
    if !extract_zip && dest.is_file() {
        info!(
            %plugin_id,
            file = file_name,
            path = %dest.display(),
            "插件资源已存在，跳过下载"
        );
        return Ok(());
    }

    info!(
        %plugin_id,
        file = file_name,
        url,
        dest = %dest.display(),
        "开始下载插件资源"
    );

    let tmp = tmp_path(&dest);
    let _ = std::fs::remove_file(&tmp);

    let response = client.get(url).send().await.map_err(|error| {
        format!("下载插件文件失败 file={file_name} url={url} reason={error}；请检查网络后重试")
    })?;
    if !response.status().is_success() {
        return Err(format!(
            "下载插件文件失败 file={file_name} http={} url={url}；请稍后重试或更换网络",
            response.status()
        )
        .into());
    }

    let total = response.content_length().unwrap_or(0) as i64;
    let mut file = std::fs::File::create(&tmp).map_err(|error| {
        format!(
            "创建临时文件失败 path={} reason={error}；请检查磁盘空间与权限后重试",
            tmp.display()
        )
    })?;

    emit_progress(app, plugin_id, file_name, 0, total);
    let mut last_emit = Instant::now();
    let mut received: i64 = 0;
    let mut stream = response.bytes_stream();
    while let Some(chunk) = stream.next().await {
        let bytes = chunk.map_err(|error| {
            format!("读取下载流失败 file={file_name} reason={error}；请检查网络后重试")
        })?;
        file.write_all(&bytes).map_err(|error| {
            format!(
                "写入临时文件失败 path={} reason={error}；请检查磁盘空间后重试",
                tmp.display()
            )
        })?;
        received += bytes.len() as i64;
        if last_emit.elapsed() >= PROGRESS_EMIT_INTERVAL {
            emit_progress(app, plugin_id, file_name, received, total);
            last_emit = Instant::now();
        }
    }
    emit_progress(app, plugin_id, file_name, received, total.max(received));

    file.sync_all().map_err(|error| {
        format!(
            "刷新临时文件失败 path={} reason={error}；请检查磁盘后重试",
            tmp.display()
        )
    })?;
    drop(file);

    std::fs::rename(&tmp, &dest).map_err(|error| {
        format!(
            "完成插件文件失败 from={} to={} reason={error}；请确认目录可写后重试",
            tmp.display(),
            dest.display()
        )
    })?;
    info!(
        %plugin_id,
        file = file_name,
        bytes = received,
        path = %dest.display(),
        "插件资源下载完成"
    );

    if extract_zip {
        extract_zip_archive(&dest, install_dir)?;
        let _ = std::fs::remove_file(&dest);
        info!(
            %plugin_id,
            dir = %install_dir.display(),
            "插件 zip 已解压并删除压缩包"
        );
    }
    Ok(())
}

/// 将 zip 解压到目标目录。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-21
fn extract_zip_archive(zip_path: &std::path::Path, dest_dir: &std::path::Path) -> DingDaResult<()> {
    let file = std::fs::File::open(zip_path)
        .map_err(|error| format!("打开 zip 失败 path={} reason={error}", zip_path.display()))?;
    let mut archive = zip::ZipArchive::new(file)
        .map_err(|error| format!("读取 zip 失败 path={} reason={error}", zip_path.display()))?;
    for index in 0..archive.len() {
        let mut entry = archive
            .by_index(index)
            .map_err(|error| format!("读取 zip 条目失败 index={index} reason={error}"))?;
        let Some(rel) = entry.enclosed_name() else {
            continue;
        };
        let out_path = dest_dir.join(rel);
        if entry.is_dir() {
            std::fs::create_dir_all(&out_path).map_err(|error| {
                format!(
                    "创建解压目录失败 path={} reason={error}",
                    out_path.display()
                )
            })?;
            continue;
        }
        if let Some(parent) = out_path.parent() {
            std::fs::create_dir_all(parent).map_err(|error| {
                format!(
                    "创建解压父目录失败 path={} reason={error}",
                    parent.display()
                )
            })?;
        }
        let mut out = std::fs::File::create(&out_path).map_err(|error| {
            format!(
                "创建解压文件失败 path={} reason={error}",
                out_path.display()
            )
        })?;
        std::io::copy(&mut entry, &mut out).map_err(|error| {
            format!(
                "写入解压文件失败 path={} reason={error}",
                out_path.display()
            )
        })?;
    }
    Ok(())
}

/// 向前端推送 `plugin/progress`；失败只记日志，不中断下载。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
fn emit_progress(app: &AppHandle, plugin_id: &str, file_name: &str, received: i64, total: i64) {
    if let Err(error) = app.emit(
        PLUGIN_PROGRESS_TOPIC,
        PluginEventProgress {
            plugin_id: plugin_id.to_string(),
            received_bytes: received,
            total_bytes: total,
            file_name: file_name.to_string(),
        },
    ) {
        warn!(%error, %plugin_id, file = file_name, "推送插件下载进度失败");
        return;
    }
    debug!(
        %plugin_id,
        file = file_name,
        received_bytes = received,
        total_bytes = total,
        "插件下载进度"
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::PLUGIN_ID_OCR;

    #[tokio::test]
    async fn tracker_prevents_duplicate_start() {
        let tracker = PluginDownloadTracker::new();
        assert!(tracker.try_start(PLUGIN_ID_OCR).await);
        assert!(!tracker.try_start(PLUGIN_ID_OCR).await);
        tracker.finish(PLUGIN_ID_OCR).await;
        assert!(tracker.try_start(PLUGIN_ID_OCR).await);
    }
}
