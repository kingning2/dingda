use crate::runtime::event::{AgentEvent, StreamParser};

pub struct PlainStreamParser;

impl PlainStreamParser {
    pub fn new() -> Self {
        Self
    }
}

impl StreamParser for PlainStreamParser {
    fn feed(&mut self, chunk: &str) -> Vec<AgentEvent> {
        let trimmed = chunk.trim();
        if trimmed.is_empty() {
            return Vec::new();
        }
        vec![AgentEvent::TextDelta {
            text: trimmed.to_string(),
        }]
    }
}
