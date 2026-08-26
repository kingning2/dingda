//! 本地文本嵌入服务（fastembed + ONNX，纯本地推理）。
//!
//! 用 `EmbeddingModel::BGESmallZHV15`（BAAI/bge-small-zh-v1.5，512 维）。
//! 模型经插件安装写入缓存目录并落 `.installed`；未安装时 `try_embed_*` 返回 `None`。

use std::fmt;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

use fastembed::{EmbeddingModel, TextEmbedding, TextInitOptions};

/// bge-small-zh-v1.5 固定输出维度。
pub const EMBEDDING_DIMS: usize = 512;

/// 安装完成标记（与 config/plugins/embedding 对齐）。
pub const INSTALLED_MARKER: &str = ".installed";

/// 本地嵌入服务错误。
#[derive(Debug, Clone)]
pub enum EmbeddingError {
    /// 模型加载失败（首次需联网下载，或下载/加载出错）。
    Init(String),
    /// 单次推理失败。
    Inference(String),
}

impl fmt::Display for EmbeddingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EmbeddingError::Init(message) => write!(f, "embedding model init: {message}"),
            EmbeddingError::Inference(message) => write!(f, "embedding inference: {message}"),
        }
    }
}

impl std::error::Error for EmbeddingError {}

/// 文本嵌入能力。
pub trait Embedder: Send + Sync {
    fn dims(&self) -> usize;

    /// 预热模型（首次会下载）；成功后写入 `.installed`。
    fn preload(&self) -> Result<(), EmbeddingError>;

    fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, EmbeddingError>;

    fn embed_text(&self, text: &str) -> Result<Vec<f32>, EmbeddingError> {
        self.embed_texts(&[text.to_string()])
            .map(|mut vectors| vectors.pop().unwrap_or_default())
    }
}

/// fastembed 实现：懒加载模型，`&self` 可并发安全调用。
pub struct EmbeddingService {
    model: OnceLock<Result<Mutex<TextEmbedding>, EmbeddingError>>,
    cache_dir: PathBuf,
}

impl EmbeddingService {
    /// 构造服务（不加载模型；首次 `preload` / `embed` 时初始化）。
    pub fn new(cache_dir: PathBuf) -> Self {
        Self {
            model: OnceLock::new(),
            cache_dir,
        }
    }

    /// 缓存目录是否已有安装标记。
    pub fn is_installed(&self) -> bool {
        self.cache_dir.join(INSTALLED_MARKER).is_file()
    }

    fn mark_installed(&self) -> Result<(), EmbeddingError> {
        std::fs::create_dir_all(&self.cache_dir).map_err(|error| {
            EmbeddingError::Init(format!(
                "create embedding cache dir {}: {error}",
                self.cache_dir.display()
            ))
        })?;
        let marker = self.cache_dir.join(INSTALLED_MARKER);
        std::fs::write(&marker, b"ok").map_err(|error| {
            EmbeddingError::Init(format!(
                "write installed marker {}: {error}",
                marker.display()
            ))
        })
    }

    fn get_model(&self) -> Result<&Mutex<TextEmbedding>, EmbeddingError> {
        self.model
            .get_or_init(|| {
                let options = TextInitOptions::new(EmbeddingModel::BGESmallZHV15)
                    .with_show_download_progress(true)
                    .with_cache_dir(self.cache_dir.clone());
                TextEmbedding::try_new(options)
                    .map(Mutex::new)
                    .map_err(|error| EmbeddingError::Init(error.to_string()))
            })
            .as_ref()
            .map_err(Clone::clone)
    }

    /// 未安装返回 `None`；已安装则嵌入。
    pub fn try_embed_text(&self, text: &str) -> Result<Option<Vec<f32>>, EmbeddingError> {
        if !self.is_installed() {
            return Ok(None);
        }
        self.embed_text(text).map(Some)
    }

    /// 未安装返回 `None`；已安装则批量嵌入。
    pub fn try_embed_texts(
        &self,
        texts: &[String],
    ) -> Result<Option<Vec<Vec<f32>>>, EmbeddingError> {
        if !self.is_installed() {
            return Ok(None);
        }
        self.embed_texts(texts).map(Some)
    }

    /// 缓存目录（测试 / 诊断）。
    pub fn cache_dir(&self) -> &Path {
        &self.cache_dir
    }
}

impl Embedder for EmbeddingService {
    fn dims(&self) -> usize {
        EMBEDDING_DIMS
    }

    fn preload(&self) -> Result<(), EmbeddingError> {
        self.get_model().map(|_| ())?;
        self.mark_installed()
    }

    fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>, EmbeddingError> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }
        let model = self.get_model()?;
        let mut model = model
            .lock()
            .map_err(|_| EmbeddingError::Inference("embedding model poisoned".into()))?;
        let refs: Vec<&str> = texts.iter().map(String::as_str).collect();
        model
            .embed(refs, None)
            .map_err(|error| EmbeddingError::Inference(error.to_string()))
    }
}
