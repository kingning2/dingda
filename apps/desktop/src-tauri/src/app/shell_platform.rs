//! 桌面 OS 平台标签：由 Rust 注入 Webview，供前端 TitleBar 等读取。
//!

//! 作者：coisini
//! 创建时间：2026-07-21

/// 当前运行 OS 对应的桌面平台标签（与前端 `DesktopPlatform` 对齐）。
///
/// 作者：coisini
/// 创建时间：2026-07-21
///
/// # 返回值
/// `"macos"` / `"windows"` / `"linux"`。
pub fn desktop_platform_label() -> &'static str {
    match std::env::consts::OS {
        "macos" => "macos",
        "windows" => "windows",
        _ => "linux",
    }
}

/// 在页面脚本执行前注入 `window.__DINGDA_PLATFORM__` 的初始化脚本。
///
/// 作者：coisini
/// 创建时间：2026-07-21
///
/// # 返回值
/// 可传给 `append_invoke_initialization_script` 的 JS 字符串。
pub fn platform_initialization_script() -> String {
    format!(
        r#"Object.defineProperty(window,"__DINGDA_PLATFORM__",{{value:"{}",writable:false,configurable:false}});"#,
        desktop_platform_label()
    )
}
