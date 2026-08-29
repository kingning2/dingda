//! 插件下载协调 — 检测安装状态，并在用户触发时下载。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19

use crate::config::{
    find_builtin, find_camoufox_executable, tmp_path, ConfigStore, PluginFetch, PluginVerify,
    PLUGIN_ID_EMBEDDING,
};
use crate::contracts::DingDaResult;
use crate::contracts::{PluginEventProgress, PluginItem};
use crate::infrastructure::embedding::{Embedder, EmbeddingService};
use futures_util::StreamExt;
use reqwest::header::{CONTENT_RANGE, RANGE};
use reqwest::StatusCode;
use std::collections::HashSet;
use std::io::Write;
use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};
use tokio::fs::OpenOptions;
use tokio::io::{AsyncSeekExt, AsyncWriteExt};
use tokio::sync::{Mutex, Semaphore};

/// 进度事件最短间隔，避免每个 chunk 都刷前端。
const PROGRESS_EMIT_INTERVAL: Duration = Duration::from_millis(120);

/// 并行分片下载：每个 Range 请求的目标分片大小。
const DOWNLOAD_CHUNK_SIZE: u64 = 8 * 1024 * 1024; // 8MiB

/// 并行分片下载：最多并发多少个 Range 请求。
const DOWNLOAD_MAX_CONCURRENCY: usize = 6;

/// 插件下载进度事件 topic（与前端 `PLUGIN_PROGRESS_EVENT` 对齐；Tauri 禁止 `.`）。
pub const PLUGIN_PROGRESS_TOPIC: &str = "plugin/progress";

fn parse_total_from_content_range(value: &str) -> Option<u64> {
    // e.g. "bytes 0-0/12345"
    let total_str = value.split('/').nth(1)?.trim();
    total_str.parse::<u64>().ok()
}

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
        .unwrap_or_else(|| crate::contracts::PluginItem {
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
    let plugin = find_builtin(plugin_id)?;
    if plugin.is_installed(store.plugins_dir(), &store.legacy_ocr_dir()) {
        info!(%plugin_id, "插件已安装，跳过下载");
        return Ok(());
    }

    match plugin.fetch {
        PluginFetch::EmbeddingModel => install_embedding_plugin(app, store).await,
        PluginFetch::Http {
            assets,
            timeout_secs,
            verify,
        } => {
            if assets.is_empty() {
                return Err(format!("当前平台暂不支持 {} 插件下载", plugin.name).into());
            }
            let install_dir = store.plugin_install_dir(plugin.id);
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

            let client = reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(timeout_secs))
                .build()
                .map_err(|error| {
                    format!("创建下载客户端失败 reason={error}；请检查本机 TLS 配置后重试")
                })?;

            for asset in assets {
                download_asset(
                    &client,
                    app,
                    plugin.id,
                    &install_dir,
                    asset.file_name,
                    asset.url,
                    asset.extract_zip,
                )
                .await?;
            }

            match verify {
                PluginVerify::None => Ok(()),
                PluginVerify::CamoufoxExe => {
                    let exe = find_camoufox_executable(store.plugins_dir()).ok_or_else(|| {
                        format!(
                            "Camoufox 解压后未找到可执行文件 path={}；请卸载后重试下载",
                            install_dir.display()
                        )
                    })?;
                    info!(path = %exe.display(), "Camoufox 可执行文件已就绪");
                    sync_camoufox_env(store);
                    Ok(())
                }
            }
        }
    }
}

/// 经 fastembed 下载 bge-small-zh-v1.5 到插件目录（走托管 EmbeddingService.preload）。
async fn install_embedding_plugin(app: &AppHandle, store: &ConfigStore) -> DingDaResult<()> {
    let install_dir = store.plugin_install_dir(PLUGIN_ID_EMBEDDING);
    info!(
        path = %install_dir.display(),
        "开始下载 Embedding 模型（bge-small-zh-v1.5）"
    );
    std::fs::create_dir_all(&install_dir).map_err(|error| {
        format!(
            "创建 Embedding 目录失败 path={} reason={error}；请检查本地数据目录权限后重试",
            install_dir.display()
        )
    })?;

    // 契约 total_bytes 为 i64（非 Option）；Embedding 无真实字节流，用 0→100 表示阶段
    let _ = app.emit(
        PLUGIN_PROGRESS_TOPIC,
        PluginEventProgress {
            plugin_id: PLUGIN_ID_EMBEDDING.to_string(),
            received_bytes: 0,
            total_bytes: 100,
            file_name: "bge-small-zh-v1.5".to_string(),
        },
    );

    let service = app.state::<Arc<EmbeddingService>>().inner().clone();
    tokio::task::spawn_blocking(move || service.preload())
        .await
        .map_err(|error| format!("Embedding 下载任务失败 reason={error}"))?
        .map_err(|error| format!("Embedding 模型下载失败 reason={error}；请检查网络后重试"))?;

    let _ = app.emit(
        PLUGIN_PROGRESS_TOPIC,
        PluginEventProgress {
            plugin_id: PLUGIN_ID_EMBEDDING.to_string(),
            received_bytes: 100,
            total_bytes: 100,
            file_name: "bge-small-zh-v1.5".to_string(),
        },
    );
    info!(path = %install_dir.display(), "Embedding 模型已就绪");
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

    // 尝试走 Range 并行分片；若探测失败则自动回退到旧的顺序下载逻辑。
    let received =
        match download_asset_range_parallel(client, app, plugin_id, &tmp, file_name, url).await? {
            Some(received) => received,
            None => download_asset_streaming(client, app, plugin_id, &tmp, file_name, url).await?,
        };

    let file = std::fs::File::open(&tmp).map_err(|error| {
        format!(
            "打开临时文件失败 path={} reason={error}；请检查磁盘空间与权限后重试",
            tmp.display()
        )
    })?;
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

async fn download_asset_streaming(
    client: &reqwest::Client,
    app: &AppHandle,
    plugin_id: &str,
    tmp: &std::path::Path,
    file_name: &str,
    url: &str,
) -> DingDaResult<i64> {
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
    let mut file = std::fs::File::create(tmp).map_err(|error| {
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
    Ok(received)
}

async fn download_asset_range_parallel(
    client: &reqwest::Client,
    app: &AppHandle,
    plugin_id: &str,
    tmp: &std::path::Path,
    file_name: &str,
    url: &str,
) -> DingDaResult<Option<i64>> {
    // 探测 Range 支持并获取总长度（Content-Range）。
    let probe = match client.get(url).header(RANGE, "bytes=0-0").send().await {
        Ok(resp) => resp,
        Err(_error) => {
            // 探测失败通常意味着 Range 不可用；回退到顺序下载以保证可用性。
            return Ok(None);
        }
    };

    if probe.status() != StatusCode::PARTIAL_CONTENT {
        return Ok(None);
    }

    let total = probe
        .headers()
        .get(CONTENT_RANGE)
        .and_then(|v| v.to_str().ok())
        .and_then(parse_total_from_content_range);

    let Some(total) = total else {
        // 不具备必要信息时直接回退。
        return Ok(None);
    };

    // 小文件并行开销更高，直接回退顺序下载。
    if total < DOWNLOAD_CHUNK_SIZE * 2 {
        return Ok(None);
    }

    let chunk_count = total.div_ceil(DOWNLOAD_CHUNK_SIZE);
    if chunk_count < 2 {
        return Ok(None);
    }

    let max_concurrency = DOWNLOAD_MAX_CONCURRENCY.min(chunk_count as usize);
    let semaphore = Arc::new(Semaphore::new(max_concurrency));

    // 预分配 .part 文件大小，便于随机 offset 写入。
    let pre = std::fs::File::create(tmp).map_err(|error| {
        format!(
            "创建临时文件失败 path={} reason={error}；请检查磁盘空间与权限后重试",
            tmp.display()
        )
    })?;
    pre.set_len(total).map_err(|error| {
        format!(
            "预分配临时文件失败 path={} size={} reason={error}；请检查磁盘空间后重试",
            tmp.display(),
            total
        )
    })?;
    drop(pre);

    let received = Arc::new(AtomicI64::new(0));
    let last_emit_ms = Arc::new(AtomicU64::new(0));
    let start_instant = Instant::now();
    let total_i64 = total as i64;

    emit_progress(app, plugin_id, file_name, 0, total_i64);

    let tmp_path = tmp.to_path_buf();
    let mut handles = Vec::with_capacity(chunk_count as usize);

    for chunk_idx in 0..chunk_count {
        let start = chunk_idx * DOWNLOAD_CHUNK_SIZE;
        let end = (start + DOWNLOAD_CHUNK_SIZE - 1).min(total - 1);

        let client = client.clone();
        let url = url.to_string();
        let app = app.clone();
        let plugin_id = plugin_id.to_string();
        let file_name = file_name.to_string();
        let tmp_path = tmp_path.clone();
        let semaphore = semaphore.clone();
        let received = received.clone();
        let last_emit_ms = last_emit_ms.clone();

        handles.push(tokio::spawn(async move {
            let _permit = semaphore
                .acquire_owned()
                .await
                .map_err(|error| format!("获取并发许可失败 reason={error}"))?;

            let resp = client
                .get(&url)
                .header(RANGE, format!("bytes={}-{}", start, end))
                .send()
                .await
                .map_err(|error| {
                    format!(
                        "下载 Range 失败 file={} range={}-{} reason={error}；请检查网络后重试",
                        file_name, start, end
                    )
                })?;

            if resp.status() != StatusCode::PARTIAL_CONTENT {
                return Err(format!(
                    "服务器未按 Range 返回部分内容 file={} range={}-{} http={}；将回退顺序下载",
                    file_name,
                    start,
                    end,
                    resp.status()
                ));
            }

            let mut file = OpenOptions::new()
                .write(true)
                .open(&tmp_path)
                .await
                .map_err(|error| {
                    format!(
                        "打开临时文件失败 path={} reason={error}；请检查磁盘后重试",
                        tmp_path.display()
                    )
                })?;
            file.seek(std::io::SeekFrom::Start(start))
                .await
                .map_err(|error| {
                    format!(
                        "seek 临时文件失败 path={} offset={} reason={error}",
                        tmp_path.display(),
                        start
                    )
                })?;

            let mut stream = resp.bytes_stream();
            let mut local_received: i64 = 0;
            while let Some(chunk) = stream.next().await {
                let bytes = chunk.map_err(|error| {
                    format!(
                        "读取 Range 流失败 file={} range={}-{} reason={error}；请检查网络后重试",
                        file_name, start, end
                    )
                })?;
                file.write_all(&bytes).await.map_err(|error| {
                    format!(
                        "写入临时文件失败 path={} offset={} reason={error}；请检查磁盘后重试",
                        tmp_path.display(),
                        start + local_received as u64
                    )
                })?;

                let added = bytes.len() as i64;
                local_received += added;
                let new_received = received.fetch_add(added, Ordering::Relaxed) + added;

                // 节流：尽量按 120ms 间隔推送进度。
                let elapsed_ms = start_instant.elapsed().as_millis() as u64;
                let prev = last_emit_ms.load(Ordering::Relaxed);
                if elapsed_ms.saturating_sub(prev) >= PROGRESS_EMIT_INTERVAL.as_millis() as u64
                    && last_emit_ms
                        .compare_exchange(prev, elapsed_ms, Ordering::Relaxed, Ordering::Relaxed)
                        .is_ok()
                {
                    emit_progress(&app, &plugin_id, &file_name, new_received, total_i64);
                }
            }

            Ok::<(), String>(())
        }));
    }

    for handle in handles {
        handle
            .await
            .map_err(|error| format!("分片下载任务 join 失败 reason={error}"))??;
    }

    let received_bytes = received.load(Ordering::Relaxed);
    emit_progress(app, plugin_id, file_name, received_bytes, total_i64);
    Ok(Some(received_bytes))
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
