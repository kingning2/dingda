//! 渠道 IO 适配器（WSS bridge + Sidecar RPC 客户端绑定）。

pub mod wss_bridge;

pub use wss_bridge::PythonWssBridge;
