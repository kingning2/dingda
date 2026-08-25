//! 共享内存传输层 — Rust 写端（客户端）实现。
//!
//! 请求流程：CAS 认领空闲槽 → 写入请求 → 置 REQ_READY（Release）→ 自适应
//! 轮询等待 RES_READY（Acquire）→ 读出响应 → 归位 IDLE。同步不依赖命名
//! 信号量，Windows / macOS / Linux 行为一致。
//!
//! # 内存安全说明
//!
//! 映射内存仅通过构造时派生的原始指针访问：字段一律经原子类型读写，
//! 缓冲区拷贝受状态机 Release/Acquire 序保护，且各槽位区域互不重叠，
//! 因此并发访问无需可变引用。

use std::fs::OpenOptions;
use std::path::Path;
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use memmap2::MmapMut;

use super::protocol::{
    self, slot_field, STATE_IDLE, STATE_REQ_READY, STATE_RES_READY, STATE_WRITING,
};

/// 单次共享内存调用整体超时（`DINGDA_SIDECAR_CALL_TIMEOUT_MS`，默认 30s）。
///
/// 防止 Python 卡死时业务调用永久挂起；超时即放弃该槽，槽位由后续
/// Sidecar 重启（Python 启动时归位全部 IDLE）统一回收。
pub fn call_timeout() -> Duration {
    std::env::var("DINGDA_SIDECAR_CALL_TIMEOUT_MS")
        .ok()
        .and_then(|value| value.parse().ok())
        .map(Duration::from_millis)
        .unwrap_or(Duration::from_secs(30))
}

/// 传输层错误。
#[derive(Debug, thiserror::Error)]
pub enum ShmTransportError {
    /// 段文件无法创建、打开或映射。
    #[error("共享内存段不可用: {0}")]
    Segment(String),
    /// 协议头 magic / version 不匹配。
    #[error("共享内存协议头无效")]
    InvalidHeader,
    /// payload 超过槽缓冲区容量。
    #[error("payload 超过缓冲区容量 {cap} 字节")]
    PayloadTooLarge {
        /// 容量上限（字节）。
        cap: usize,
    },
    /// 等待期间观察到槽位被归位 IDLE —— Sidecar 已重启并重置段。
    #[error("Sidecar 在调用期间重启，本次请求被丢弃")]
    SidecarRestarted,
    /// 等待响应超过整体 deadline，放弃本次调用。
    #[error("Sidecar 调用超时（{timeout:?}）")]
    Timeout {
        /// 超时上限。
        timeout: Duration,
    },
}

/// 兼容 HTTP 语义的响应：状态码 + JSON 字节。
#[derive(Debug)]
pub struct ShmResponse {
    /// 响应状态码（200 / 404 / 500 ...）。
    pub status: u32,
    /// 响应体字节（JSON 文本）。
    pub body: Vec<u8>,
}

/// 共享内存传输端点；多任务并发安全（槽位级 CAS 认领）。
#[derive(Clone)]
pub struct ShmTransport {
    inner: Arc<Inner>,
}

struct Inner {
    /// 保持映射存活；所有读写经 `ptr` 原子访问。
    _map: MmapMut,
    ptr: *mut u8,
    len: usize,
}

// SAFETY: 所有访问都经由原始指针上的原子操作或受状态机保护的缓冲区拷贝，
// 无跨线程别名引用。
unsafe impl Send for Inner {}
unsafe impl Sync for Inner {}

impl ShmTransport {
    /// 创建（或重建）共享内存段文件并初始化协议头。
    ///
    /// 头部其余字段由文件截断清零保证：heartbeat=0、ready=0、全部槽位 IDLE。
    pub fn create(path: &Path) -> Result<Self, ShmTransportError> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(true)
            .open(path)
            .map_err(|error| ShmTransportError::Segment(error.to_string()))?;
        file.set_len(protocol::segment_size() as u64)
            .map_err(|error| ShmTransportError::Segment(error.to_string()))?;

        // SAFETY: 文件长度已覆盖整段映射范围。
        let mut map = unsafe { MmapMut::map_mut(&file) }
            .map_err(|error| ShmTransportError::Segment(error.to_string()))?;
        let ptr = map.as_mut_ptr();
        let len = map.len();
        let inner = Arc::new(Inner {
            _map: map,
            ptr,
            len,
        });

        let transport = Self { inner };
        transport.copy_in(0, &protocol::MAGIC[..]);
        transport.write_u32(0x08, protocol::VERSION);
        transport.write_u32(0x0C, protocol::SLOT_COUNT);
        Ok(transport)
    }

    /// 打开既有段并校验协议头。
    pub fn open(path: &Path) -> Result<Self, ShmTransportError> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(path)
            .map_err(|error| ShmTransportError::Segment(error.to_string()))?;
        // SAFETY: 双方按协议约定写入各自区域，映射为读写。
        let mut map = unsafe { MmapMut::map_mut(&file) }
            .map_err(|error| ShmTransportError::Segment(error.to_string()))?;
        let ptr = map.as_mut_ptr();
        let len = map.len();
        let inner = Arc::new(Inner {
            _map: map,
            ptr,
            len,
        });
        let transport = Self { inner };
        transport.verify_header()?;
        Ok(transport)
    }

    fn verify_header(&self) -> Result<(), ShmTransportError> {
        let bytes = self.bytes();
        if bytes.len() < protocol::HEADER_SIZE
            || bytes.get(0..8) != Some(protocol::MAGIC.as_slice())
        {
            return Err(ShmTransportError::InvalidHeader);
        }
        if self.read_u32(0x08) != protocol::VERSION {
            return Err(ShmTransportError::InvalidHeader);
        }
        Ok(())
    }

    /// Sidecar 存活判定：服务循环已就绪且心跳未过期。
    #[must_use]
    pub fn is_healthy(&self) -> bool {
        if self.read_u64(0x18) != 1 {
            return false;
        }
        let heartbeat = self.read_u64(0x10);
        let now_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|value| value.as_millis() as u64)
            .unwrap_or(0);
        now_ms.saturating_sub(heartbeat) < protocol::HEARTBEAT_TIMEOUT_MS
    }

    fn bytes(&self) -> &[u8] {
        // SAFETY: 指针与长度来自有效映射，且映射在 Arc 内存活整个生命周期。
        unsafe { std::slice::from_raw_parts(self.inner.ptr, self.inner.len) }
    }

    fn read_u32(&self, offset: usize) -> u32 {
        self.atomic_u32(offset).load(Ordering::Relaxed)
    }

    fn read_u64(&self, offset: usize) -> u64 {
        self.atomic_u64(offset).load(Ordering::Relaxed)
    }

    fn write_u32(&self, offset: usize, value: u32) {
        self.atomic_u32(offset).store(value, Ordering::Relaxed);
    }

    fn atomic_u32(&self, offset: usize) -> &AtomicU32 {
        debug_assert_eq!(offset % 4, 0, "u32 字段必须 4 字节对齐");
        debug_assert!(offset + 4 <= self.inner.len, "u32 字段不得越界");
        // SAFETY: 对齐与越界已断言；原子引用生命周期绑定 &self。
        unsafe { &*(self.inner.ptr.add(offset) as *const AtomicU32) }
    }

    fn atomic_u64(&self, offset: usize) -> &AtomicU64 {
        debug_assert_eq!(offset % 8, 0, "u64 字段必须 8 字节对齐");
        debug_assert!(offset + 8 <= self.inner.len, "u64 字段不得越界");
        // SAFETY: 对齐与越界已断言；原子引用生命周期绑定 &self。
        unsafe { &*(self.inner.ptr.add(offset) as *const AtomicU64) }
    }

    fn copy_in(&self, offset: usize, src: &[u8]) {
        debug_assert!(offset + src.len() <= self.inner.len, "写入不得越界");
        // SAFETY: 越界已断言；目标缓冲区受状态机保护，无并发读者。
        unsafe {
            std::ptr::copy_nonoverlapping(src.as_ptr(), self.inner.ptr.add(offset), src.len())
        };
    }

    fn copy_out(&self, offset: usize, len: usize) -> Vec<u8> {
        debug_assert!(offset + len <= self.inner.len, "读取不得越界");
        let mut out = vec![0u8; len];
        // SAFETY: 越界已断言；数据由对方的 Release 发布、本方 Acquire 可见。
        unsafe { std::ptr::copy_nonoverlapping(self.inner.ptr.add(offset), out.as_mut_ptr(), len) };
        out
    }

    /// 发送一次请求并等待响应（阻塞）。`payload` 为已序列化的 JSON envelope。
    pub fn call_blocking(&self, payload: &[u8]) -> Result<ShmResponse, ShmTransportError> {
        if payload.len() > protocol::REQ_CAP {
            return Err(ShmTransportError::PayloadTooLarge {
                cap: protocol::REQ_CAP,
            });
        }
        self.verify_header()?;

        // 轮询发牌游标 + CAS 抢空闲槽；全忙则退避后重来。
        let count = protocol::SLOT_COUNT;
        let start = self.atomic_u32(0x20).fetch_add(1, Ordering::Relaxed);
        let (index, state) = 'claim: loop {
            for step in 0..count {
                let index = (u64::from(start) + u64::from(step)) % u64::from(count);
                let index = index as u32;
                let base = protocol::slot_offset(index);
                let state = self.atomic_u32(base + slot_field::STATE);
                if state
                    .compare_exchange(
                        STATE_IDLE,
                        STATE_WRITING,
                        Ordering::AcqRel,
                        Ordering::Acquire,
                    )
                    .is_ok()
                {
                    break 'claim (index, state);
                }
            }
            std::thread::sleep(Duration::from_millis(1));
        };

        let base = protocol::slot_offset(index);
        self.atomic_u64(base + slot_field::REQ_SEQ)
            .fetch_add(1, Ordering::Relaxed);
        self.atomic_u32(base + slot_field::REQ_LEN)
            .store(payload.len() as u32, Ordering::Relaxed);
        self.copy_in(base + slot_field::REQ_BUF, payload);
        // Release 发布请求载荷。
        state.store(STATE_REQ_READY, Ordering::Release);

        let timeout = call_timeout();
        let deadline = Instant::now() + timeout;
        let mut backoff = Duration::from_micros(50);
        loop {
            match state.load(Ordering::Acquire) {
                STATE_RES_READY => break,
                STATE_IDLE => return Err(ShmTransportError::SidecarRestarted),
                _ => {
                    if Instant::now() >= deadline {
                        return Err(ShmTransportError::Timeout { timeout });
                    }
                    std::thread::sleep(backoff);
                    backoff = (backoff * 2).min(Duration::from_millis(5));
                }
            }
        }

        let res_len = self
            .atomic_u32(base + slot_field::RES_LEN)
            .load(Ordering::Acquire) as usize;
        let status = self.read_u32(base + slot_field::STATUS);
        if res_len > protocol::RES_CAP {
            state.store(STATE_IDLE, Ordering::Release);
            return Err(ShmTransportError::Segment(format!(
                "响应长度非法: {res_len}"
            )));
        }
        let body = self.copy_out(base + slot_field::RES_BUF, res_len);
        state.store(STATE_IDLE, Ordering::Release);

        Ok(ShmResponse { status, body })
    }
}
