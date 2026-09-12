//! Camoufox 浏览器运行时的定位与解压。
//!
//! 职责：
//!     从打包 resources 的 zip 解压到 `~/.dingda/v2/camoufox/current`，
//!     并对外提供可执行文件路径；壳把它注入 `DINGDA_CAMOUFOX_EXE` 给 Python 侧。
//!
//! 设计说明：
//!     - 本包是「Camoufox 能力」的唯一落点，删掉本包即等于去掉 Camoufox 支持
//!     - `find_camoufox_exe` 原本放在 paths 包，因它是 Camoufox 专属知识，
//!       迁入本包以打断 paths ↔ camoufox 的循环依赖
//!     - 只做定位与解压，不启动浏览器

mod camoufox;

pub use camoufox::{
    bundled_camoufox_zip, camoufox_platform_tag, ensure_camoufox_exe, extract_camoufox_zip,
    find_camoufox_exe,
};
