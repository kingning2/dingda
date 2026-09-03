//! 桌面 OS 平台标签 — 供前端自定义标题栏布局（macOS / Windows / Linux）。

/// 与前端 `DesktopPlatform` 对齐的平台字符串。
pub fn desktop_platform_label() -> &'static str {
    match std::env::consts::OS {
        "macos" => "macos",
        "windows" => "windows",
        _ => "linux",
    }
}

/// 在 WebView 脚本执行前注入 `window.__DINGDA_PLATFORM__`。
pub fn platform_initialization_script() -> String {
    format!(
        r#"Object.defineProperty(window,"__DINGDA_PLATFORM__",{{value:"{}",writable:false,configurable:false}});"#,
        desktop_platform_label()
    )
}
