//! Rust ↔ Python 连接层 — 长连接管道（Named Pipe / Unix Socket）与共享内存载荷通道。
//!
//! 业务只依赖 [`IpcSession`] / [`super::SidecarClient`] / [`ShmTransport`]；
//! 不得直接操作平台管道。

pub mod endpoint;
pub mod error;
pub mod framing;
pub mod protocol;
pub mod session;
pub mod shm;
pub mod transport;

#[cfg(windows)]
mod named_pipe;
#[cfg(unix)]
mod unix_socket;

pub use endpoint::IpcEndpoint;
pub use error::IpcError;
pub use protocol::{RpcError, RpcEvent, RpcRequest, RpcResponse, WireMessage};
pub use session::IpcSession;
pub use shm::{ShmResponse, ShmTransport, ShmTransportError};
pub use transport::Transport;
