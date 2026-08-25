//! 搜索业务 IPC（闲鱼 / 1688）。

#[cfg(platform_ali1688)]
mod ali1688;
#[cfg(platform_xianyu)]
mod xianyu;

#[cfg(platform_ali1688)]
pub use ali1688::ali1688_search;
#[cfg(platform_xianyu)]
pub use xianyu::xianyu_search;
