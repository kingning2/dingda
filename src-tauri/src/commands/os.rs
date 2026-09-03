#[tauri::command]
pub async fn show_in_folder(path: String) -> Result<(), String> {
    tauri_plugin_opener::reveal_item_in_dir(path).map_err(|error| error.to_string())
}
