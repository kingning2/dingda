//! 共享内存布局常量 — 必须与 `python/runtime/shm_protocol.py` 严格一致。
//!
//! 段结构：
//!
//! ```text
//! [header: HEADER_SIZE]
//! [slot 0][slot 1]...[slot N-1]
//! ```
//!
//! header（小端）：
//!
//! ```text
//! 0x00 [u8;8]  magic = b"DINGSHM\x01"
//! 0x08 u32     version
//! 0x0C u32     slot_count
//! 0x10 u64     heartbeat_ms（Python 每 ~250ms 更新）
//! 0x18 u64     ready_flag（Python 服务循环就绪后置 1）
//! 0x20 u32     next_slot（Rust 写端轮询发牌游标）
//! 0x24 u32     reserved
//! ```
//!
//! 每个槽位（小端）：
//!
//! ```text
//! +0x00 u32 state（状态机，见 STATE_*）
//! +0x04 u32 req_len
//! +0x08 u32 res_len
//! +0x0C u32 status（兼容 HTTP 语义：200 / 404 / 500 ...）
//! +0x10 u64 req_seq
//! +0x18 u64 res_seq
//! +0x20 [u8; REQ_CAP] req_buf
//! +..   [u8; RES_CAP] res_buf
//! ```

/// 段文件 magic。
pub const MAGIC: &[u8; 8] = b"DINGSHM\x01";
/// 协议版本。
pub const VERSION: u32 = 1;
/// 头部字节数。
pub const HEADER_SIZE: usize = 64;
/// 槽位数量。
pub const SLOT_COUNT: u32 = 16;
/// 单个请求缓冲区容量。
pub const REQ_CAP: usize = 1024 * 1024;
/// 单个响应缓冲区容量。
pub const RES_CAP: usize = 1024 * 1024;

const SLOT_HDR_SIZE: usize = 32;

/// 槽状态：空闲，可被 Rust 写端认领。
pub const STATE_IDLE: u32 = 0;
/// 槽状态：Rust 正在写入请求。
pub const STATE_WRITING: u32 = 1;
/// 槽状态：请求就绪，等待 Python 认领处理。
pub const STATE_REQ_READY: u32 = 2;
/// 槽状态：Python 正在处理。
pub const STATE_PROCESSING: u32 = 3;
/// 槽状态：响应就绪，等待 Rust 读取后归位 IDLE。
pub const STATE_RES_READY: u32 = 4;

/// 心跳过期阈值：超过该时长未更新视为 Sidecar 失联。
pub const HEARTBEAT_TIMEOUT_MS: u64 = 5_000;

/// 单槽字节数。
#[must_use]
pub fn slot_size() -> usize {
    SLOT_HDR_SIZE + REQ_CAP + RES_CAP
}

/// 段总字节数。
#[must_use]
pub fn segment_size() -> usize {
    HEADER_SIZE + usize::try_from(SLOT_COUNT).expect("slot count fits") * slot_size()
}

/// 第 `index` 个槽位的起始偏移。
#[must_use]
pub fn slot_offset(index: u32) -> usize {
    HEADER_SIZE + usize::try_from(index).expect("slot index fits") * slot_size()
}

/// 槽内各字段相对槽基址的偏移。
pub mod slot_field {
    use super::SLOT_HDR_SIZE;
    use super::{REQ_CAP, RES_CAP};

    /// 状态机字。
    pub const STATE: usize = 0;
    /// 请求长度。
    pub const REQ_LEN: usize = 4;
    /// 响应长度。
    pub const RES_LEN: usize = 8;
    /// 响应状态码。
    pub const STATUS: usize = 12;
    /// 请求序号（单调递增，观测用）。
    pub const REQ_SEQ: usize = 16;
    /// 响应序号。
    pub const RES_SEQ: usize = 24;
    /// 请求缓冲区。
    pub const REQ_BUF: usize = SLOT_HDR_SIZE;
    /// 响应缓冲区。
    pub const RES_BUF: usize = SLOT_HDR_SIZE + REQ_CAP;

    // 保证缓冲区不越出槽边界。
    const _: () = assert!(RES_BUF + RES_CAP == SLOT_HDR_SIZE + REQ_CAP + RES_CAP);
}
// 共享内存传输层 — Rust 写端（客户端）实现。
//
// 请求流程：CAS 认领空闲槽 → 写入请求 → 置 REQ_READY（Release）→ 自适应
// 轮询等待 RES_READY（Acquire）→ 读出响应 → 归位 IDLE。同步不依赖命名
// 信号量，Windows / macOS / Linux 行为一致。
//
// # 内存安全说明
//
// 映射内存仅通过构造时派生的原始指针访问：字段一律经原子类型读写，
// 缓冲区拷贝受状态机 Release/Acquire 序保护，且各槽位区域互不重叠，
// 因此并发访问无需可变引用。

use std::fs::OpenOptions;
use std::path::Path;
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use memmap2::MmapMut;

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
        file.set_len(segment_size() as u64)
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
        transport.copy_in(0, &MAGIC[..]);
        transport.write_u32(0x08, VERSION);
        transport.write_u32(0x0C, SLOT_COUNT);
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
        if bytes.len() < HEADER_SIZE || bytes.get(0..8) != Some(MAGIC.as_slice()) {
            return Err(ShmTransportError::InvalidHeader);
        }
        if self.read_u32(0x08) != VERSION {
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
        now_ms.saturating_sub(heartbeat) < HEARTBEAT_TIMEOUT_MS
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

    /// 认领槽位并写入请求，置 `REQ_READY` 后返回槽索引（阻塞）。
    ///
    /// 调用方应立刻经管道发送 `shm.wake`，再 [`Self::wait_slot`]。
    pub fn submit(&self, payload: &[u8]) -> Result<u32, ShmTransportError> {
        if payload.len() > REQ_CAP {
            return Err(ShmTransportError::PayloadTooLarge { cap: REQ_CAP });
        }
        self.verify_header()?;

        let count = SLOT_COUNT;
        let start = self.atomic_u32(0x20).fetch_add(1, Ordering::Relaxed);
        let (index, state) = 'claim: loop {
            for step in 0..count {
                let index = (u64::from(start) + u64::from(step)) % u64::from(count);
                let index = index as u32;
                let base = slot_offset(index);
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

        let base = slot_offset(index);
        self.atomic_u64(base + slot_field::REQ_SEQ)
            .fetch_add(1, Ordering::Relaxed);
        self.atomic_u32(base + slot_field::REQ_LEN)
            .store(payload.len() as u32, Ordering::Relaxed);
        self.copy_in(base + slot_field::REQ_BUF, payload);
        state.store(STATE_REQ_READY, Ordering::Release);
        Ok(index)
    }

    /// 等待指定槽位进入 `RES_READY` 并读出响应（阻塞）。
    pub fn wait_slot(&self, index: u32) -> Result<ShmResponse, ShmTransportError> {
        if index >= SLOT_COUNT {
            return Err(ShmTransportError::Segment(format!("非法槽位 {index}")));
        }
        let base = slot_offset(index);
        let state = self.atomic_u32(base + slot_field::STATE);
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
        if res_len > RES_CAP {
            state.store(STATE_IDLE, Ordering::Release);
            return Err(ShmTransportError::Segment(format!(
                "响应长度非法: {res_len}"
            )));
        }
        let body = self.copy_out(base + slot_field::RES_BUF, res_len);
        state.store(STATE_IDLE, Ordering::Release);
        Ok(ShmResponse { status, body })
    }

    /// 写入请求后经 `notify(slot)` 唤醒 Python，再等待响应（阻塞）。
    pub fn call_blocking_with_notify<F>(
        &self,
        payload: &[u8],
        notify: F,
    ) -> Result<ShmResponse, ShmTransportError>
    where
        F: FnOnce(u32) -> Result<(), String>,
    {
        let index = self.submit(payload)?;
        if let Err(error) = notify(index) {
            return Err(ShmTransportError::Segment(format!(
                "shm.wake 失败: {error}"
            )));
        }
        self.wait_slot(index)
    }

    /// 无唤醒回调的阻塞调用（仅测试 / 兜底；生产应带 notify）。
    pub fn call_blocking(&self, payload: &[u8]) -> Result<ShmResponse, ShmTransportError> {
        self.call_blocking_with_notify(payload, |_| Ok(()))
    }
}
