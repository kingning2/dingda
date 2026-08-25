//! 利润判定 — 本地利润率为硬门槛，AI 只复核边界案例与同款匹配度。

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// 单个商品的最终判定。
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct ItemVerdict {
    /// 是否值得入库。
    pub keep: bool,
    /// AI 估算的闲鱼可售价（元）。
    pub est_sell_price: f64,
    /// AI 估算的 1688 供货价（元）。
    pub est_cost_price: f64,
    /// 同款置信度（1688 货源是否真为同款）：high / medium / low。
    pub same_item_confidence: String,
    /// 一句话理由。
    pub reason: String,
}

/// 构造复核 prompt：附带本地比价数据，让 AI 只判断「同款可信度 + 是否值得入库」。
pub fn build_verdict_prompt(criteria: &str, candidate_json: &str, quote_json: &str) -> String {
    let schema = serde_json::to_string(&schemars::schema_for!(ItemVerdict))
        .unwrap_or_else(|_| "{}".to_string());
    format!(
        "你是跨平台选品助手。闲鱼商品与 1688 货源如下，请判断：\
         1) 货源是否为同款（型号/成色/配置差异要指出）；\
         2) 结合估算价差，是否值得入库。\n\
         只输出符合以下 JSON Schema 的单个 JSON 对象，不要其它文字：\n{schema}\n\
         选品标准：{criteria}\n\
         闲鱼商品：{candidate_json}\n\
         1688 最低货源：{quote_json}"
    )
}

/// 解析 AI 返回的判定结果。
pub fn parse_verdict(raw: &str) -> Result<ItemVerdict, String> {
    serde_json::from_str(raw.trim())
        .map_err(|error| format!("AI 判定 JSON 解析失败: {error}; raw={raw}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_verdict() {
        let raw = r#"{"keep":true,"est_sell_price":130,"est_cost_price":90,
            "same_item_confidence":"high","reason":"同款且价差充足"}"#;
        let verdict = parse_verdict(raw).expect("parse");
        assert!(verdict.keep);
        assert_eq!(verdict.same_item_confidence, "high");
    }

    #[test]
    fn rejects_missing_field() {
        assert!(parse_verdict(r#"{"keep":true}"#).is_err());
    }
}
