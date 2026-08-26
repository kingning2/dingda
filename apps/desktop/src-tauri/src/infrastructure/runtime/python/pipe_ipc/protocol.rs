//! MessagePack 线协议消息（Request / Response / Event）。

use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcRequest {
    pub id: u64,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcError {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcResponse {
    pub id: u64,
    pub success: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<RpcError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcEvent {
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

/// 线消息 — `type` 字段区分三类。
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum WireMessage {
    Request {
        id: u64,
        method: String,
        #[serde(default)]
        params: Value,
    },
    Response {
        id: u64,
        success: bool,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        result: Option<Value>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        error: Option<RpcError>,
    },
    Event {
        method: String,
        #[serde(default)]
        params: Value,
    },
}

impl WireMessage {
    pub fn encode(&self) -> Result<Vec<u8>, String> {
        rmp_serde::to_vec_named(self).map_err(|e| e.to_string())
    }

    pub fn decode(bytes: &[u8]) -> Result<Self, String> {
        rmp_serde::from_slice(bytes).map_err(|e| e.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::WireMessage;

    #[test]
    fn wire_message_roundtrip_request() {
        let msg = WireMessage::Request {
            id: 42,
            method: "runtime.ping".into(),
            params: serde_json::json!({}),
        };
        let bytes = msg.encode().expect("encode");
        let decoded = WireMessage::decode(&bytes).expect("decode");
        match decoded {
            WireMessage::Request { id, method, .. } => {
                assert_eq!(id, 42);
                assert_eq!(method, "runtime.ping");
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn wire_message_roundtrip_event() {
        let msg = WireMessage::Event {
            method: "runtime.ready".into(),
            params: serde_json::json!({}),
        };
        let bytes = msg.encode().expect("encode");
        let decoded = WireMessage::decode(&bytes).expect("decode");
        match decoded {
            WireMessage::Event { method, .. } => assert_eq!(method, "runtime.ready"),
            other => panic!("unexpected {other:?}"),
        }
    }
}
