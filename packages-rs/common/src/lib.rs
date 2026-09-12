//! 壳的共享基础层：日志出口、路径解析、平台标签。
//!
//! 本包不含任何产品业务能力，被 camoufox / python / runtime / agent 与壳共同依赖。
//! 改日志格式、路径规则、平台判定都在这里改。

pub mod logging;
pub mod paths;
pub mod platform;
