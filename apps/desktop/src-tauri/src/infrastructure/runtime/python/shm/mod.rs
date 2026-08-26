//! Rust ↔ Python 共享内存载荷通道（预留大文件；产品默认走 pipe）。

pub mod protocol;
pub mod transport;

pub use transport::{ShmResponse, ShmTransport, ShmTransportError};
