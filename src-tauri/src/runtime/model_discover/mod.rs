pub mod acp;
pub mod common;
pub mod dsh;

pub use acp::{discover_acp_models, AcpDiscoveryConfig};
pub use common::{
    parse_codex_debug_models, parse_cursor_models, parse_id_label_lines, parse_opencode_models,
    parse_pi_models, parse_plain_id_lines, run_command, static_models,
};
pub use dsh::discover_dsh_models;
