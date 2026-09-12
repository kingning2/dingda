//! models.dev 公共目录：给没有「列模型」子命令的 CLI 兜模型元数据。
//!
//! 目前只服务 Claude —— `claude` CLI 没有列模型的入口，账号侧可用模型也取不到，
//! 所以用 models.dev 的 anthropic provider 目录代替；拉不到时由调用方回落静态列表。

use std::collections::HashSet;

use crate::runtime::defs::base::fetch_text;
use crate::runtime::types::RuntimeModel;

const MODELS_DEV_URL: &str = "https://models.dev/api.json";
const ANTHROPIC_PROVIDER: &str = "anthropic";

/// 拉 models.dev 的 anthropic 目录；网络失败或格式变化时返回空。
pub async fn fetch_models_dev_anthropic() -> Vec<RuntimeModel> {
    match fetch_text(MODELS_DEV_URL).await {
        Ok(text) => parse_models_dev_anthropic(&text),
        Err(_) => Vec::new(),
    }
}

/// 解析 `providers.anthropic.models`（以模型 id 为键的对象），`name` 做 label。
///
/// 取不到就返回空 vec，由调用方决定兜底。
///
/// 注：`serde_json` 未开 `preserve_order`，模型按键字母序而非 models.dev 原始顺序。
pub fn parse_models_dev_anthropic(json: &str) -> Vec<RuntimeModel> {
    let Ok(parsed) = serde_json::from_str::<serde_json::Value>(json) else {
        return Vec::new();
    };
    let Some(models) = parsed
        .get("providers")
        .and_then(|providers| providers.get(ANTHROPIC_PROVIDER))
        .and_then(|provider| provider.get("models"))
        .and_then(|models| models.as_object())
    else {
        return Vec::new();
    };

    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for (raw_id, raw) in models {
        let id = raw_id.trim();
        if id.is_empty() || !seen.insert(id.to_string()) {
            continue;
        }
        let label = raw
            .get("name")
            .and_then(|value| value.as_str())
            .map(str::trim)
            .filter(|name| !name.is_empty())
            .unwrap_or(id)
            .to_string();
        out.push(RuntimeModel {
            id: id.to_string(),
            label,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::parse_models_dev_anthropic;

    const SAMPLE: &str = r#"{
        "providers": {
            "anthropic": {
                "id": "anthropic",
                "models": {
                    "claude-sonnet-4-6": {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
                    "claude-haiku-4-5": {"id": "claude-haiku-4-5"}
                }
            },
            "openai": {"models": {"gpt-5": {"name": "GPT-5"}}}
        }
    }"#;

    #[test]
    fn reads_anthropic_models_with_label_fallback() {
        let models = parse_models_dev_anthropic(SAMPLE);
        assert_eq!(models.len(), 2);
        // 字母序：haiku 在 sonnet 前
        assert_eq!(models[0].id, "claude-haiku-4-5");
        assert_eq!(models[0].label, "claude-haiku-4-5");
        assert_eq!(models[1].id, "claude-sonnet-4-6");
        assert_eq!(models[1].label, "Claude Sonnet 4.6");
    }

    #[test]
    fn ignores_other_providers() {
        let models = parse_models_dev_anthropic(SAMPLE);
        assert!(models.iter().all(|model| model.id != "gpt-5"));
    }

    #[test]
    fn missing_provider_or_models_is_empty() {
        assert!(parse_models_dev_anthropic(r#"{"providers":{}}"#).is_empty());
        assert!(parse_models_dev_anthropic(r#"{"providers":{"anthropic":{}}}"#).is_empty());
    }

    #[test]
    fn empty_models_object_is_empty() {
        assert!(
            parse_models_dev_anthropic(r#"{"providers":{"anthropic":{"models":{}}}}"#).is_empty()
        );
    }

    #[test]
    fn garbage_input_is_empty() {
        assert!(parse_models_dev_anthropic("not json").is_empty());
        assert!(parse_models_dev_anthropic("").is_empty());
        assert!(parse_models_dev_anthropic("[]").is_empty());
    }
}
