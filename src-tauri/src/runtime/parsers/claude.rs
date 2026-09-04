use serde_json::Value;

use crate::runtime::event::{AgentEvent, StreamParser};
use crate::runtime::parsers::parse_json_line;

pub struct ClaudeStreamParser {
    session_id: Option<String>,
}

impl ClaudeStreamParser {
    pub fn new(_runtime_id: &str, _run_id: &str) -> Self {
        Self { session_id: None }
    }
}

impl StreamParser for ClaudeStreamParser {
    fn feed(&mut self, chunk: &str) -> Vec<AgentEvent> {
        let mut events = Vec::new();
        for line in chunk.lines() {
            let Some(value) = parse_json_line(line) else {
                continue;
            };
            for event in map_claude_json(&value) {
                match event {
                    AgentEvent::Session { session_id } => {
                        if self.session_id.as_ref() != Some(&session_id) {
                            self.session_id = Some(session_id.clone());
                            events.push(AgentEvent::Session { session_id });
                        }
                    }
                    other => events.push(other),
                }
            }
        }
        events
    }
}

pub fn map_claude_json(value: &Value) -> Vec<AgentEvent> {
    let mut out = Vec::new();
    let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    match event_type {
        "system" => {
            let subtype = value.get("subtype").and_then(|v| v.as_str()).unwrap_or("");
            if subtype == "init" {
                if let Some(session_id) = value
                    .get("session_id")
                    .or_else(|| value.get("sessionId"))
                    .and_then(|v| v.as_str())
                    .filter(|id| !id.is_empty())
                {
                    out.push(AgentEvent::Session {
                        session_id: session_id.to_string(),
                    });
                }
            }
        }
        "result" => {
            if let Some(session_id) = value
                .get("session_id")
                .or_else(|| value.get("sessionId"))
                .and_then(|v| v.as_str())
                .filter(|id| !id.is_empty())
            {
                out.push(AgentEvent::Session {
                    session_id: session_id.to_string(),
                });
            }
            if let Some(err) = value.get("error").and_then(|v| v.as_str()) {
                out.push(AgentEvent::Error {
                    message: err.to_string(),
                });
            }
        }
        "assistant" => {
            if let Some(message) = value.get("message") {
                extract_content_blocks(message, &mut out);
            }
        }
        "content_block_delta" => {
            let delta_type = value
                .pointer("/delta/type")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let text = value
                .pointer("/delta/text")
                .or_else(|| value.pointer("/delta/thinking"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if text.is_empty() {
                return out;
            }
            if delta_type == "thinking_delta" {
                out.push(AgentEvent::Thinking {
                    text: text.to_string(),
                });
            } else {
                out.push(AgentEvent::TextDelta {
                    text: text.to_string(),
                });
            }
        }
        "content_block_start" => {
            if value.pointer("/content_block/type").and_then(|v| v.as_str()) == Some("tool_use") {
                let block = value.get("content_block").unwrap_or(value);
                let id = block
                    .get("id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let name = block
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let input = block.get("input").cloned().unwrap_or(Value::Null);
                out.push(AgentEvent::ToolCall { id, name, input });
            }
        }
        _ => {}
    }

    out
}

fn extract_content_blocks(message: &Value, out: &mut Vec<AgentEvent>) {
    let Some(blocks) = message.get("content").and_then(|v| v.as_array()) else {
        return;
    };
    for block in blocks {
        let block_type = block.get("type").and_then(|v| v.as_str()).unwrap_or("");
        match block_type {
            "text" => {
                if let Some(text) = block.get("text").and_then(|v| v.as_str()) {
                    out.push(AgentEvent::TextDelta {
                        text: text.to_string(),
                    });
                }
            }
            "thinking" => {
                if let Some(text) = block.get("thinking").and_then(|v| v.as_str()) {
                    out.push(AgentEvent::Thinking {
                        text: text.to_string(),
                    });
                }
            }
            "tool_use" => {
                let id = block
                    .get("id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let name = block
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let input = block.get("input").cloned().unwrap_or(Value::Null);
                out.push(AgentEvent::ToolCall { id, name, input });
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_system_init_session() {
        let raw = json!({
            "type": "system",
            "subtype": "init",
            "session_id": "claude-ses-1"
        });
        let events = map_claude_json(&raw);
        match &events[0] {
            AgentEvent::Session { session_id } => assert_eq!(session_id, "claude-ses-1"),
            _ => panic!("expected session"),
        }
    }

    #[test]
    fn parse_content_block_delta_text() {
        let raw = json!({
            "type": "content_block_delta",
            "delta": { "type": "text_delta", "text": "hello" }
        });
        let events = map_claude_json(&raw);
        match &events[0] {
            AgentEvent::TextDelta { text } => assert_eq!(text, "hello"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn parse_assistant_tool_use() {
        let raw = json!({
            "type": "assistant",
            "message": {
                "content": [
                    { "type": "tool_use", "id": "t1", "name": "Read", "input": { "path": "a.rs" } }
                ]
            }
        });
        let events = map_claude_json(&raw);
        match &events[0] {
            AgentEvent::ToolCall { name, .. } => assert_eq!(name, "Read"),
            _ => panic!("expected tool call"),
        }
    }
}
