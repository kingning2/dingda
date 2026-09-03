use serde_json::Value;

use crate::runtime::event::{AgentEvent, StreamParser};
use crate::runtime::parsers::parse_json_line;

pub struct CodexStreamParser;

impl CodexStreamParser {
    pub fn new(_runtime_id: &str, _run_id: &str) -> Self {
        Self
    }
}

impl StreamParser for CodexStreamParser {
    fn feed(&mut self, chunk: &str) -> Vec<AgentEvent> {
        let mut events = Vec::new();
        for line in chunk.lines() {
            let Some(value) = parse_json_line(line) else {
                continue;
            };
            events.extend(map_codex_json(&value));
        }
        events
    }
}

pub fn map_codex_json(value: &Value) -> Vec<AgentEvent> {
    let mut out = Vec::new();
    let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    match event_type {
        "thread.started" => {}
        "item.completed" | "message" => {
            if let Some(text) = value.pointer("/item/text").and_then(|v| v.as_str()) {
                out.push(AgentEvent::TextDelta {
                    text: text.to_string(),
                });
            }
            if let Some(text) = value.pointer("/message/content").and_then(|v| v.as_str()) {
                out.push(AgentEvent::TextDelta {
                    text: text.to_string(),
                });
            }
            if let Some(item_type) = value.pointer("/item/type").and_then(|v| v.as_str()) {
                if item_type == "reasoning" {
                    if let Some(text) = value.pointer("/item/summary").and_then(|v| v.as_str()) {
                        out.push(AgentEvent::Thinking {
                            text: text.to_string(),
                        });
                    }
                }
            }
        }
        "response.output_text.delta" | "response.reasoning_summary_text.delta" => {
            let field = if event_type.contains("reasoning") {
                "thinking"
            } else {
                "text"
            };
            if let Some(delta) = value.get("delta").and_then(|v| v.as_str()) {
                if field == "thinking" {
                    out.push(AgentEvent::Thinking {
                        text: delta.to_string(),
                    });
                } else {
                    out.push(AgentEvent::TextDelta {
                        text: delta.to_string(),
                    });
                }
            }
        }
        "reasoning" | "reasoning.delta" => {
            if let Some(text) = value.get("delta").and_then(|v| v.as_str()) {
                out.push(AgentEvent::Thinking {
                    text: text.to_string(),
                });
            }
        }
        "tool_call" | "function_call" | "item.tool_call" => {
            let id = value
                .get("id")
                .or_else(|| value.get("call_id"))
                .or_else(|| value.pointer("/item/call_id"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let name = value
                .get("name")
                .or_else(|| value.pointer("/function/name"))
                .or_else(|| value.pointer("/item/name"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let input = value
                .get("arguments")
                .or_else(|| value.get("input"))
                .or_else(|| value.pointer("/item/input"))
                .cloned()
                .unwrap_or(Value::Null);
            out.push(AgentEvent::ToolCall { id, name, input });
        }
        "error" => {
            if let Some(msg) = value.get("message").and_then(|v| v.as_str()) {
                out.push(AgentEvent::Error {
                    message: msg.to_string(),
                });
            }
        }
        _ => {}
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_output_text_delta() {
        let raw = json!({
            "type": "response.output_text.delta",
            "delta": "hi"
        });
        let events = map_codex_json(&raw);
        match &events[0] {
            AgentEvent::TextDelta { text } => assert_eq!(text, "hi"),
            _ => panic!("expected text delta"),
        }
    }

    #[test]
    fn parse_item_completed_text() {
        let raw = json!({
            "type": "item.completed",
            "item": { "type": "message", "text": "done" }
        });
        let events = map_codex_json(&raw);
        match &events[0] {
            AgentEvent::TextDelta { text } => assert_eq!(text, "done"),
            _ => panic!("expected text"),
        }
    }
}
