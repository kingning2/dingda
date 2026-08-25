//! Rust ↔ Python 共享内存 IPC（遗留；内部通道已切换为 [`super::pipe_ipc`]）。
//!
//! 协议见 [`protocol`]；传输见 [`transport`]。

pub mod protocol;
pub mod transport;

pub use transport::{ShmResponse, ShmTransport, ShmTransportError};
