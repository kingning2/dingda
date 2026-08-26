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
