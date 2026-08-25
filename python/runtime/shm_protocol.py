"""共享内存布局常量 — 与 Rust `core/manager/python/shm/protocol.rs` 严格一致。

段结构:

```text
[header: HEADER_SIZE]
[slot 0][slot 1]...[slot N-1]
```

header（小端）:

```text
0x00 [u8;8]  magic = b"DINGSHM\x01"
0x08 u32     version
0x0C u32     slot_count
0x10 u64     heartbeat_ms（Python 每 ~250ms 更新）
0x18 u64     ready_flag（Python 服务循环就绪后置 1）
0x20 u32     next_slot（Rust 写端轮询发牌游标）
0x24 u32     reserved
```

每个槽位（小端）:

```text
+0x00 u32 state（状态机，见 STATE_*）
+0x04 u32 req_len
+0x08 u32 res_len
+0x0C u32 status（兼容 HTTP 语义：200 / 404 / 500 ...）
+0x10 u64 req_seq
+0x18 u64 res_seq
+0x20 [u8; REQ_CAP] req_buf
+..   [u8; RES_CAP] res_buf
```

注意：`mmap` 按字节偏移读写，本文件只声明常量与偏移辅助函数，
不依赖任何第三方库。
"""

from __future__ import annotations

# 段文件 magic。
MAGIC: bytes = b"DINGSHM\x01"
# 协议版本。
VERSION: int = 1
# 头部字节数。
HEADER_SIZE: int = 64
# 槽位数量。
SLOT_COUNT: int = 16
# 单个请求缓冲区容量。
REQ_CAP: int = 1024 * 1024
# 单个响应缓冲区容量。
RES_CAP: int = 1024 * 1024

# 槽内固定头部（状态/长度/状态码/序号）字节数。
SLOT_HDR_SIZE: int = 32

# 槽状态：空闲，可被 Rust 写端认领。
STATE_IDLE: int = 0
# 槽状态：Rust 正在写入请求。
STATE_WRITING: int = 1
# 槽状态：请求就绪，等待 Python 认领处理。
STATE_REQ_READY: int = 2
# 槽状态：Python 正在处理。
STATE_PROCESSING: int = 3
# 槽状态：响应就绪，等待 Rust 读取后归位 IDLE。
STATE_RES_READY: int = 4

# 心跳过期阈值：超过该时长未更新视为 Sidecar 失联（与 Rust 一致）。
HEARTBEAT_TIMEOUT_MS: int = 5_000

# header 字段偏移。
OFF_VERSION: int = 0x08
OFF_SLOT_COUNT: int = 0x0C
OFF_HEARTBEAT: int = 0x10
OFF_READY: int = 0x18
OFF_NEXT_SLOT: int = 0x20

# 槽内字段相对槽基址的偏移。
STATE: int = 0
REQ_LEN: int = 4
RES_LEN: int = 8
STATUS: int = 12
REQ_SEQ: int = 16
RES_SEQ: int = 24
REQ_BUF: int = SLOT_HDR_SIZE
RES_BUF: int = SLOT_HDR_SIZE + REQ_CAP

# 单槽字节数。
SLOT_SIZE: int = SLOT_HDR_SIZE + REQ_CAP + RES_CAP
# 段总字节数。
SEGMENT_SIZE: int = HEADER_SIZE + SLOT_COUNT * SLOT_SIZE


def slot_offset(index: int) -> int:
    """第 `index` 个槽位的起始偏移。"""
    return HEADER_SIZE + index * SLOT_SIZE
