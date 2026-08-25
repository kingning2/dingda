//! 回复引擎 — 意图 → 上下文 → LLM 生成 → 议价控制。
//!
//! 渠道无关：业务层（crates/app）传入消息、商品知识、对话历史与账号 AI 设置，
//! 引擎负责意图检测、议价轮数控制、提示词组装、provider 分发与结果归一化。
//!
//! 流程（对齐 Python 版 ai_reply_engine）：
//! 1. 检查 AI 是否启用（设置 + 时间范围）；
//! 2. 本地意图检测（price / tech / default）；
//! 3. 议价上限检查（达到上限返回固定拒绝话术）；
//! 4. 组装 system + user 提示词（商品信息 + 历史 + 议价设置）；
//! 5. 按 provider 类型分发到对应实现；
//! 6. 返回生成回复（截断时重试一次）。

use chrono::{Local, Timelike};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::intent::{self, Intent};
use crate::knowledge::ItemKnowledge;
use crate::model::{
    normalize_provider_type, provider_from_settings, ChatMessage, ChatRequest, LlmError,
    LlmProvider, ProviderSettings,
};
use crate::prompt::PromptBuilder;

/// 达到议价上限时的固定拒绝话术。
pub const BARGAIN_LIMIT_REPLY: &str = "抱歉，这个价格已经是最优惠的了，不能再便宜了哦！";

/// AI 回复设置（账号级，对齐 Python `ai_reply_settings`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiSettings {
    pub ai_enabled: bool,
    pub provider_type: String,
    pub api_key: String,
    pub base_url: String,
    pub model_name: String,
    pub max_bargain_rounds: u32,
    pub max_discount_percent: u32,
    pub max_discount_amount: u32,
    /// 自定义提示词（按意图覆盖，JSON 对象）。
    pub custom_prompts: Value,
    /// 启用时间范围（HH:MM，空表示不限）。
    pub time_range_start: String,
    pub time_range_end: String,
}

impl Default for AiSettings {
    fn default() -> Self {
        Self {
            ai_enabled: false,
            provider_type: "openai_compatible".to_string(),
            api_key: String::new(),
            base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1".to_string(),
            model_name: "qwen-plus".to_string(),
            max_bargain_rounds: 3,
            max_discount_percent: 10,
            max_discount_amount: 100,
            custom_prompts: Value::Object(Default::default()),
            time_range_start: String::new(),
            time_range_end: String::new(),
        }
    }
}

impl AiSettings {
    /// 规范化 provider 类型（兼容旧配置缺字段场景）。
    pub fn normalized_provider_type(&self) -> String {
        normalize_provider_type(&self.provider_type, &self.base_url, &self.model_name)
    }

    /// 是否在启用时间范围内（北京时间；空范围视为不限）。
    pub fn in_time_range(&self) -> bool {
        let now = Local::now();
        let now_min = now.hour() * 60 + now.minute();
        self.in_time_range_at(now_min)
    }

    /// 以"当日分钟"判定时间范围（可测试）。
    pub fn in_time_range_at(&self, now_min: u32) -> bool {
        let (start, end) = (self.time_range_start.trim(), self.time_range_end.trim());
        if start.is_empty() || end.is_empty() {
            return true;
        }
        match (parse_hhmm(start), parse_hhmm(end)) {
            (Some(start_min), Some(end_min)) => {
                if start_min <= end_min {
                    now_min >= start_min && now_min <= end_min
                } else {
                    // 跨天（22:00 → 06:00）。
                    now_min >= start_min || now_min <= end_min
                }
            }
            _ => true,
        }
    }

    /// 转为 provider 连接设置。
    pub fn to_provider_settings(&self) -> ProviderSettings {
        ProviderSettings {
            provider_type: self.normalized_provider_type(),
            api_key: self.api_key.clone(),
            base_url: self.base_url.clone(),
            model: self.model_name.clone(),
        }
    }
}

/// 解析 `HH:MM[:SS]` 为当日分钟数。
fn parse_hhmm(value: &str) -> Option<u32> {
    let parts: Vec<&str> = value.split(':').collect();
    let hour: u32 = parts.first()?.parse().ok()?;
    let minute: u32 = parts.get(1).copied().unwrap_or("0").parse().ok()?;
    Some(hour * 60 + minute)
}

/// 回复引擎上下文（业务层注入）。
pub struct ReplyContext<'a> {
    pub user_message: &'a str,
    pub item: &'a ItemKnowledge,
    /// 对话历史（最近 N 条，按时间升序）。
    pub history: &'a [ChatMessage],
    /// 当前议价次数（历史中 price 意图 user 消息计数）。
    pub bargain_count: u32,
    pub settings: &'a AiSettings,
}

/// 回复结果。
#[derive(Debug, Clone)]
pub enum ReplyOutcome {
    /// AI 未启用 / 配置缺失 / 超出时间范围。
    Disabled,
    /// 达到议价上限（固定拒绝话术）。
    BargainLimited,
    /// 生成成功。
    Generated(String),
    /// 生成失败（调用错误）。
    Failed(String),
}

/// 回复引擎。
pub struct ReplyEngine;

impl ReplyEngine {
    /// 生成 AI 回复。`skip_wait` 语义由业务层控制，引擎本身无等待。
    pub async fn generate(context: &ReplyContext<'_>) -> ReplyOutcome {
        let settings = context.settings;

        // 1. 启用检查。
        if !settings.ai_enabled {
            return ReplyOutcome::Disabled;
        }
        if settings.api_key.trim().is_empty() {
            warn!("AI 已启用但 api_key 未配置，跳过 AI 回复");
            return ReplyOutcome::Disabled;
        }
        if !settings.in_time_range() {
            info!(
                start = %settings.time_range_start,
                end = %settings.time_range_end,
                "当前时间不在 AI 启用时间段内，跳过 AI 回复"
            );
            return ReplyOutcome::Disabled;
        }

        // 2. 意图检测。
        let intent = intent::route_intent(context.user_message);
        info!(?intent, "本地意图检测");

        // 3. 议价上限检查。
        if intent == Intent::Price && context.bargain_count >= settings.max_bargain_rounds {
            info!(
                bargain_count = context.bargain_count,
                max = settings.max_bargain_rounds,
                "议价次数已达上限"
            );
            return ReplyOutcome::BargainLimited;
        }

        // 4. 组装提示词。
        let system = PromptBuilder::system_prompt(intent.as_str(), &settings.custom_prompts);
        let item_context = context.item.to_context();
        let history = context
            .history
            .iter()
            .map(|msg| format!("{}: {}", msg.role, msg.content))
            .collect::<Vec<_>>()
            .join("\n");
        let user = PromptBuilder::user_prompt(
            &item_context,
            &history,
            context.bargain_count,
            settings.max_bargain_rounds,
            settings.max_discount_percent,
            settings.max_discount_amount,
            context.user_message,
        );

        let request = ChatRequest {
            model: settings.model_name.clone(),
            messages: vec![ChatMessage::system(system), ChatMessage::user(user)],
            max_tokens: 8192,
            temperature: 0.5,
            disable_thinking: false,
            ..Default::default()
        };

        // 5. provider 分发。
        let provider_settings = settings.to_provider_settings();
        let provider = match provider_from_settings(&provider_settings) {
            Ok(provider) => provider,
            Err(error) => return ReplyOutcome::Failed(error.to_string()),
        };
        info!(
            provider = provider.kind(),
            model = %settings.model_name,
            "调用 LLM 生成回复"
        );

        match Self::complete_with_retry_on_truncation(provider.as_ref(), &request).await {
            Ok(reply) => {
                info!(reply = %truncate(&reply, 50), "AI 回复生成成功");
                ReplyOutcome::Generated(reply)
            }
            Err(error) => {
                error!(%error, "AI 回复生成失败");
                ReplyOutcome::Failed(error.to_string())
            }
        }
    }

    /// 补全；finish_reason=length（截断）时放大 max_tokens 重试一次。
    async fn complete_with_retry_on_truncation(
        provider: &dyn LlmProvider,
        request: &ChatRequest,
    ) -> Result<String, LlmError> {
        let response = provider.complete(request).await?;
        let truncated = response
            .finish_reason
            .as_deref()
            .is_some_and(|reason| reason.contains("length"));

        if !truncated {
            return Ok(response.reply);
        }

        warn!("LLM 输出被截断，放大 max_tokens 重试一次");
        let mut retry = request.clone();
        retry.max_tokens = request.max_tokens.saturating_mul(2).max(1024);
        let retry_response = provider.complete(&retry).await?;
        if retry_response.reply.trim().is_empty() {
            return Err(LlmError::EmptyResponse);
        }
        Ok(retry_response.reply)
    }
}

/// 日志用截断。
fn truncate(text: &str, limit: usize) -> String {
    if text.chars().count() <= limit {
        return text.to_string();
    }
    let head: String = text.chars().take(limit).collect();
    format!("{head}...")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::ChatMessage;

    fn settings() -> AiSettings {
        AiSettings {
            ai_enabled: true,
            api_key: String::from("k"),
            model_name: "m".to_string(),
            ..Default::default()
        }
    }

    fn context<'a>(
        message: &'a str,
        settings: &'a AiSettings,
        bargain_count: u32,
        item: &'a ItemKnowledge,
    ) -> ReplyContext<'a> {
        ReplyContext {
            user_message: message,
            item,
            history: &[],
            bargain_count,
            settings,
        }
    }

    #[tokio::test]
    async fn disabled_when_ai_off() {
        let settings = AiSettings {
            ai_enabled: false,
            ..Default::default()
        };
        let item = ItemKnowledge::default();
        let ctx = context("便宜点", &settings, 0, &item);
        assert!(matches!(
            ReplyEngine::generate(&ctx).await,
            ReplyOutcome::Disabled
        ));
    }

    #[tokio::test]
    async fn disabled_without_api_key() {
        let settings = AiSettings {
            ai_enabled: true,
            api_key: "".to_string(),
            ..Default::default()
        };
        let item = ItemKnowledge::default();
        let ctx = context("便宜点", &settings, 0, &item);
        assert!(matches!(
            ReplyEngine::generate(&ctx).await,
            ReplyOutcome::Disabled
        ));
    }

    #[tokio::test]
    async fn bargain_limited_at_cap() {
        let settings = settings();
        let item = ItemKnowledge::default();
        let ctx = context("能便宜点吗", &settings, 3, &item);
        assert!(matches!(
            ReplyEngine::generate(&ctx).await,
            ReplyOutcome::BargainLimited
        ));
    }

    #[test]
    fn time_range_parsing() {
        let settings = AiSettings {
            time_range_start: "22:00".to_string(),
            time_range_end: "06:00".to_string(),
            ..Default::default()
        };
        // 跨天范围：22:00 后与 06:00 前命中。
        assert!(settings.in_time_range_at(23 * 60));
        assert!(settings.in_time_range_at(3 * 60));
        assert!(!settings.in_time_range_at(12 * 60));

        // 常规范围：09:00-18:00。
        let work = AiSettings {
            time_range_start: "09:00".to_string(),
            time_range_end: "18:00".to_string(),
            ..Default::default()
        };
        assert!(work.in_time_range_at(10 * 60));
        assert!(!work.in_time_range_at(20 * 60));

        // 空范围不限。
        let open = AiSettings {
            time_range_start: "".to_string(),
            time_range_end: "".to_string(),
            ..Default::default()
        };
        assert!(open.in_time_range_at(0));
    }

    #[test]
    fn provider_type_normalization() {
        let settings = AiSettings {
            provider_type: "claude".to_string(),
            ..Default::default()
        };
        assert_eq!(settings.normalized_provider_type(), "anthropic");
    }

    #[test]
    fn history_formatting() {
        let history = vec![ChatMessage::user("在吗"), ChatMessage::assistant("在的")];
        let item = ItemKnowledge::default();
        let ctx = ReplyContext {
            user_message: "多少钱",
            item: &item,
            history: &history,
            bargain_count: 0,
            settings: &settings(),
        };
        assert_eq!(ctx.history.len(), 2);
    }
}
