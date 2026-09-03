use super::defs::{
    CLAUDE, CODEBUDDY, CODEX, CURSOR, DEEPSEEK, DEEPSEEK_HARNESS, GROK, MIMO, OPENCODE, PI,
    QODER, QWEN, TRAE,
};
use super::types::RuntimeDefinition;

pub const RUNTIME_REGISTRY: &[RuntimeDefinition] = &[
    CLAUDE,
    OPENCODE,
    MIMO,
    CODEX,
    CURSOR,
    DEEPSEEK_HARNESS,
    QWEN,
    QODER,
    DEEPSEEK,
    GROK,
    PI,
    TRAE,
    CODEBUDDY,
];

pub fn find_runtime(runtime_id: &str) -> Option<&'static RuntimeDefinition> {
    RUNTIME_REGISTRY.iter().find(|item| item.id == runtime_id)
}

pub fn all_binary_names() -> Vec<String> {
    RUNTIME_REGISTRY
        .iter()
        .flat_map(|def| def.all_binary_names())
        .map(str::to_string)
        .collect::<std::collections::HashSet<_>>()
        .into_iter()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registry_has_unique_ids() {
        let mut seen = std::collections::HashSet::new();
        for def in RUNTIME_REGISTRY {
            assert!(seen.insert(def.id), "duplicate id: {}", def.id);
        }
    }

    #[test]
    fn find_codex() {
        assert_eq!(find_runtime("codex").unwrap().binary, "codex");
    }
}
