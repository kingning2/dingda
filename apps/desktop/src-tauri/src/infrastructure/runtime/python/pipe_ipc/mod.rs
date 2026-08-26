//! Rust ↔ Python 跨平台长连接 IPC（Named Pipe / Unix Domain Socket）。
//!
//! 业务只依赖 [`IpcSession`] / [`SidecarClient`]；不得直接操作平台管道。

pub mod endpoint;
pub mod error;
pub mod framing;
pub mod protocol;
pub mod session;
pub mod transport;

pub use endpoint::IpcEndpoint;
pub use error::IpcError;
pub use protocol::{RpcError, RpcEvent, RpcRequest, RpcResponse, WireMessage};
pub use session::IpcSession;
pub use transport::Transport;
