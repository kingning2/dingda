mod claude;
mod codex;
mod json_event;
mod opencode;
mod plain;

use crate::runtime::event::StreamParser;
use crate::runtime::types::StreamFormat;

pub use claude::ClaudeStreamParser;
pub use codex::CodexStreamParser;
pub use json_event::JsonEventStreamParser;
pub use opencode::OpenCodeStreamParser;
pub use plain::PlainStreamParser;

pub fn create_parser(format: StreamFormat, runtime_id: &str, run_id: &str) -> Box<dyn StreamParser> {
    match format {
        StreamFormat::ClaudeStreamJson => Box::new(ClaudeStreamParser::new(runtime_id, run_id)),
        StreamFormat::JsonEventStream => match runtime_id {
            "codex" | "cursor-agent" | "mimo" => {
                Box::new(CodexStreamParser::new(runtime_id, run_id))
            }
            "opencode" | "byok-opencode" | "atomcode" => {
                Box::new(OpenCodeStreamParser::new(runtime_id, run_id))
            }
            _ => Box::new(JsonEventStreamParser::new(runtime_id, run_id)),
        },
        StreamFormat::QoderStreamJson => Box::new(ClaudeStreamParser::new(runtime_id, run_id)),
        StreamFormat::AcpJsonRpc | StreamFormat::PiRpc | StreamFormat::DshProfileJsonl => {
            Box::new(JsonEventStreamParser::new(runtime_id, run_id))
        }
        StreamFormat::Plain => Box::new(PlainStreamParser::new()),
    }
}

pub fn parse_json_line(line: &str) -> Option<serde_json::Value> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }
    serde_json::from_str(trimmed).ok()
}
