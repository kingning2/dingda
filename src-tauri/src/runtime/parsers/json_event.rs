use crate::runtime::event::{AgentEvent, StreamParser};
use crate::runtime::parsers::CodexStreamParser;

pub struct JsonEventStreamParser {
    inner: CodexStreamParser,
}

impl JsonEventStreamParser {
    pub fn new(runtime_id: &str, run_id: &str) -> Self {
        Self {
            inner: CodexStreamParser::new(runtime_id, run_id),
        }
    }
}

impl StreamParser for JsonEventStreamParser {
    fn feed(&mut self, chunk: &str) -> Vec<AgentEvent> {
        self.inner.feed(chunk)
    }
}
