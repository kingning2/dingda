//! Sidecar route binding: GET /v1/runtime/status (runtime snapshot).

use super::client::{SidecarClient, SidecarClientError};
use super::snapshot::PythonSidecarSnapshot;

pub async fn fetch(client: &SidecarClient) -> Result<PythonSidecarSnapshot, SidecarClientError> {
    client.get_json("/v1/runtime/status").await
}

#[cfg(test)]
mod tests {
    use crate::infrastructure::runtime::python::snapshot::PythonSidecarSnapshot;

    #[test]
    fn deserializes_minimal_snapshot() {
        let raw = r#"{"ok":true,"state":"running","uptime_ms":100}"#;
        let snap: PythonSidecarSnapshot = serde_json::from_str(raw).unwrap();
        assert!(snap.ok);
        assert_eq!(snap.state, "running");
        assert_eq!(snap.uptime_ms, 100);
        assert!(snap.active_ops.is_empty());
    }
}
