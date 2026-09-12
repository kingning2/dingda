use std::sync::Arc;

use serde::Serialize;
use tauri::State;

use python::PythonLifecycle;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ServerStatus {
    pub ready: bool,
    pub api_base_url: String,
}

#[tauri::command]
pub fn get_api_base_url(runtime: State<'_, Arc<PythonLifecycle>>) -> String {
    runtime.api_base_url()
}

#[tauri::command]
pub fn get_server_status(runtime: State<'_, Arc<PythonLifecycle>>) -> ServerStatus {
    ServerStatus {
        ready: runtime.is_ready(),
        api_base_url: runtime.api_base_url(),
    }
}
