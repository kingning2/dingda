use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

#[tauri::command]
pub async fn pick_file(app: AppHandle) -> Result<Option<String>, String> {
    let picked = tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("选择文件")
            .blocking_pick_file()
            .map(|path| path.to_string())
    })
    .await
    .map_err(|error| error.to_string())?;

    Ok(picked)
}

#[tauri::command]
pub async fn pick_folder(app: AppHandle) -> Result<Option<String>, String> {
    let picked = tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("选择文件夹")
            .blocking_pick_folder()
            .map(|path| path.to_string())
    })
    .await
    .map_err(|error| error.to_string())?;

    Ok(picked)
}
