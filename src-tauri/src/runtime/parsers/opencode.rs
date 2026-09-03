use serde_json::Value;

use crate::runtime::event::{AgentEvent, StreamParser};
use crate::runtime::parsers::parse_json_line;

pub struct OpenCodeStreamParser;

impl OpenCodeStreamParser {
    pub fn new(_runtime_id: &str, _run_id: &str) -> Self {
        Self
    }
}

impl StreamParser for OpenCodeStreamParser {
    fn feed(&mut self, chunk: &str) -> Vec<AgentEvent> {
        let mut events = Vec::new();
        for line in chunk.lines() {
            let Some(value) = parse_json_line(line) else {
                continue;
            };
            events.extend(map_opencode_json(&value));
        }
        events
    }
}

pub fn map_opencode_json(value: &Value) -> Vec<AgentEvent> {
    let mut out = Vec::new();
    let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    match event_type {
        "text" => {
            if let Some(text) = value.pointer("/part/text").and_then(|v| v.as_str()) {
                if !text.is_empty() {
                    out.push(AgentEvent::TextDelta {
                        text: text.to_string(),
                    });
                }
            }
        }
        "reasoning" => {
            if let Some(text) = value.pointer("/part/text").and_then(|v| v.as_str()) {
                if !text.is_empty() {
                    out.push(AgentEvent::Thinking {
                        text: text.to_string(),
                    });
                }
            }
        }
        "part_delta" => {
            let delta = value.get("delta").and_then(|v| v.as_str()).unwrap_or("");
            if delta.is_empty() {
                return out;
            }
            let part_type = value
                .get("partType")
                .or_else(|| value.get("part_type"))
                .and_then(|v| v.as_str())
                .unwrap_or("text");
            if part_type == "reasoning" {
                out.push(AgentEvent::Thinking {
                    text: delta.to_string(),
                });
            } else {
                out.push(AgentEvent::TextDelta {
                    text: delta.to_string(),
                });
            }
        }
        "tool_use" => {
            let part = value.get("part").unwrap_or(value);
            let id = part
                .get("callID")
                .or_else(|| part.get("call_id"))
                .or_else(|| part.get("id"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let name = part
                .get("tool")
                .and_then(|v| v.as_str())
                .unwrap_or("tool")
                .to_string();
            let input = part
                .pointer("/state/input")
                .cloned()
                .unwrap_or(Value::Null);
            out.push(AgentEvent::ToolCall {
                id: id.clone(),
                name,
                input,
            });
            if let Some(output) = part.pointer("/state/output") {
                out.push(AgentEvent::ToolResult {
                    id,
                    output: output.clone(),
                });
            }
        }
        "error" => {
            let message = value
                .pointer("/error/data/message")
                .or_else(|| value.pointer("/error/message"))
                .or_else(|| value.get("message"))
                .and_then(|v| v.as_str())
                .unwrap_or("OpenCode 执行失败");
            out.push(AgentEvent::Error {
                message: message.to_string(),
            });
        }
        "step_start" | "step_finish" => {}
        _ => {}
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_text_event() {
        let raw = json!({
            "type": "text",
            "sessionID": "ses_test",
            "part": { "type": "text", "text": "hello" }
        });
        let events = map_opencode_json(&raw);
        assert_eq!(events.len(), 1);
        match &events[0] {
            AgentEvent::TextDelta { text } => assert_eq!(text, "hello"),
            _ => panic!("expected text delta"),
        }
    }

    #[test]
    fn parse_tool_use_event() {
        let raw = json!({
            "type": "tool_use",
            "part": {
                "callID": "call_1",
                "tool": "bash",
                "state": {
                    "status": "completed",
                    "input": { "command": "ls" },
                    "output": "ok"
                }
            }
        });
        let events = map_opencode_json(&raw);
        assert_eq!(events.len(), 2);
        match &events[0] {
            AgentEvent::ToolCall { name, .. } => assert_eq!(name, "bash"),
            _ => panic!("expected tool call"),
        }
    }

    #[test]
    fn parse_part_delta_reasoning() {
        let raw = json!({
            "type": "part_delta",
            "partType": "reasoning",
            "delta": "thinking..."
        });
        let events = map_opencode_json(&raw);
        match &events[0] {
            AgentEvent::Thinking { text } => assert_eq!(text, "thinking..."),
            _ => panic!("expected thinking"),
        }
    }
}
