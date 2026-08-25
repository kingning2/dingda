//! Rust ↔ Python 共享内存 IPC — 协议布局与传输层。
//!
//! 传输协议常量见 [`protocol`]；Rust 写端实现见 [`transport`]。
//! Python 读端镜像实现在 `python/runtime/shm_protocol.py` / `shm_server.py`。

pub mod protocol;
pub mod transport;

pub use transport::{ShmResponse, ShmTransport, ShmTransportError};
