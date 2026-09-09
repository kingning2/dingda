use super::defs::{CLAUDE, CODEX, OPENCODE};
use super::types::RuntimeDefinition;

/// 产品对外暴露的本地 Agent CLI。
pub const RUNTIME_REGISTRY: &[RuntimeDefinition] = &[OPENCODE, CLAUDE, CODEX];

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
    fn registry_keeps_three_product_agents() {
        let ids: Vec<_> = RUNTIME_REGISTRY.iter().map(|d| d.id).collect();
        assert_eq!(ids, vec!["opencode", "claude", "codex"]);
    }

    #[test]
    fn find_codex() {
        assert_eq!(find_runtime("codex").unwrap().binary, "codex");
    }
}
