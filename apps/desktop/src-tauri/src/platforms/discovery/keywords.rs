//! 关键词生成与自我修正 — 基于上一轮比价结果让 AI 调整闲鱼搜索方向。

use super::DiscoveryReport;

/// 生成下一轮关键词的 prompt：携带历史轮次摘要，要求避开已饱和方向。
pub fn build_refine_prompt(criteria: &str, report: &DiscoveryReport) -> String {
    let history = report
        .rounds
        .iter()
        .map(|round| {
            format!(
                "第{}轮 关键词[{}] 过需求门槛{} 比价成功{} 入库{}",
                round.round,
                round.keywords.join(","),
                round.demand_passed,
                round.sourced,
                round.accepted
            )
        })
        .collect::<Vec<_>>()
        .join("；");

    format!(
        "你是二手平台选品助手。基于以下比价历史，生成 1~5 个新的闲鱼搜索关键词，\
         向「需求旺盛且 1688 有低价货源」的方向延伸，避开已饱和的关键词。\n\
         要求：只输出 JSON 数组，如 [\"关键词1\",\"关键词2\"]，不要其它文字。\n\
         选品标准：{criteria}\n\
         比价历史：{history}"
    )
}

/// 解析 AI 返回的关键词数组（纯解析，便于单测；容错提取由调用方完成）。
pub fn parse_keywords(raw: &str) -> Result<Vec<String>, String> {
    let parsed: Vec<String> = serde_json::from_str(raw.trim())
        .map_err(|error| format!("AI 关键词 JSON 解析失败: {error}; raw={raw}"))?;
    let keywords: Vec<String> = parsed
        .into_iter()
        .map(|item| item.trim().to_string())
        .filter(|item| !item.is_empty())
        .collect();
    if keywords.is_empty() {
        return Err("AI 未生成有效关键词".to_string());
    }
    Ok(keywords)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_keyword_array() {
        let keywords = parse_keywords(r#"["关键词1", "关键词2"]"#).expect("parse");
        assert_eq!(keywords, vec!["关键词1".to_string(), "关键词2".to_string()]);
    }

    #[test]
    fn rejects_empty_keywords() {
        assert!(parse_keywords("[]").is_err());
    }
}
