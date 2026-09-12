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
    use crate::types::AuthParse;

    #[test]
    fn registry_has_unique_ids() {
        let mut seen = std::collections::HashSet::new();
        for def in RUNTIME_REGISTRY {
            assert!(seen.insert(def.id), "duplicate id: {}", def.id);
        }
    }

    #[test]
    fn registry_keeps_product_agents() {
        let ids: Vec<_> = RUNTIME_REGISTRY.iter().map(|d| d.id).collect();
        assert_eq!(ids, vec!["opencode", "claude", "codex"]);
    }

    #[test]
    fn find_codex() {
        assert_eq!(find_runtime("codex").unwrap().binary, "codex");
    }

    #[test]
    fn codex_logs_in_via_exit_code() {
        let auth = CODEX.auth.expect("codex auth");
        assert_eq!(auth.probe_args, ["login", "status"]);
        assert_eq!(auth.login_args, ["login"]);
        assert_eq!(auth.parse, AuthParse::ExitCode);
        assert!(CODEX.can_login());
    }

    #[test]
    fn claude_logs_in_via_json_status() {
        let auth = CLAUDE.auth.expect("claude auth");
        assert_eq!(auth.probe_args, ["auth", "status"]);
        assert_eq!(auth.parse, AuthParse::JsonLoggedIn);
        assert_eq!(auth.login_args, ["auth", "login"]);
        assert!(CLAUDE.can_login());
    }

    #[test]
    fn opencode_logs_in_via_credential_count() {
        let auth = OPENCODE.auth.expect("opencode auth");
        assert_eq!(auth.probe_args, ["auth", "list"]);
        assert_eq!(auth.parse, AuthParse::CredentialCount);
        assert!(OPENCODE.can_login());
    }

    /// 声明了 auth 就必须声明探针参数，否则探针永远拿不到结论。
    #[test]
    fn every_auth_declares_a_probe() {
        for def in RUNTIME_REGISTRY {
            let Some(auth) = def.auth else { continue };
            assert!(
                !auth.probe_args.is_empty(),
                "{} 的 auth 没声明探针",
                def.id
            );
        }
    }
}
