//! 发现循环编排 — 关键词 → 闲鱼需求过滤 → 1688 比价 → 利润判定 → 入库。

use std::collections::HashSet;

use super::demand::filter_candidate;
use super::evaluate::{build_verdict_prompt, parse_verdict};
use super::keywords::{build_refine_prompt, parse_keywords};
use super::sourcing::extract_lowest_quote;
use super::{profit_ratio, DiscoveryConfig, DiscoveryReport, DiscoveryRoundSummary, SeenItems};

/// 循环依赖的端口 — 全部为回调，便于单测 mock。
///
/// `search_xianyu` / `search_ali1688` 接 sidecar 对应 channel 的搜索；
/// `call_ai` 复用 [`super::super::xianyu::monitor::ai`] 的多账号故障转移调用；
/// `store` 由上层注入（写入商品库）。
pub struct DiscoveryDeps<'a> {
    /// 闲鱼按关键词搜索，返回商品 JSON 列表。
    pub search_xianyu: Box<dyn FnMut(&str, i64) -> Result<Vec<serde_json::Value>, String> + 'a>,
    /// 1688 按关键词比价，返回货源 JSON 列表。
    pub search_ali1688: Box<dyn FnMut(&str) -> Result<Vec<serde_json::Value>, String> + 'a>,
    /// 调 LLM 并返回原始文本（已含多账号故障转移）。
    pub call_ai: Box<dyn FnMut(String) -> Result<String, String> + 'a>,
    /// 入库回调（keep=true 的商品与利润备注）。
    pub store: Box<dyn FnMut(&serde_json::Value, &str) -> Result<(), String> + 'a>,
}

/// 执行发现循环。
///
/// 终止条件：轮数预算耗尽 / AI 无新方向。每轮结束把 [`DiscoveryReport`]
/// 快照落库即可实现断点续跑（TODO(接入)：检查点持久化）。
pub async fn run(
    config: &DiscoveryConfig,
    seen: &mut SeenItems,
    deps: &mut DiscoveryDeps<'_>,
) -> Result<DiscoveryReport, String> {
    if config.seed_keywords.is_empty() {
        return Err("缺少种子关键词".to_string());
    }

    let mut report = DiscoveryReport::default();
    let mut keywords = config.seed_keywords.clone();
    let mut stale_rounds = 0u32;

    for round in 1..=config.max_rounds {
        let mut summary = DiscoveryRoundSummary {
            round,
            keywords: keywords.clone(),
            ..Default::default()
        };

        for keyword in &keywords {
            // 需求侧：闲鱼搜索 + 想要人数门槛。
            let items = (deps.search_xianyu)(keyword, config.max_results_per_keyword)?;
            summary.xianyu_scanned += items.len();
            let candidates: Vec<_> = items
                .iter()
                .filter_map(|item| filter_candidate(item, config.min_wanters))
                .filter(|candidate| seen.0.insert(candidate.item_id.clone()))
                .collect();
            summary.demand_passed += candidates.len();

            // 供给侧 + 判定。
            for candidate in candidates {
                summary.sourced += 1;
                let Some(quote) = (deps.search_ali1688)(&candidate.title)
                    .ok()
                    .as_deref()
                    .and_then(|offers| extract_lowest_quote(offers))
                else {
                    summary.rejected += 1;
                    continue;
                };

                match profit_ratio(candidate.sell_price, quote.lowest_price) {
                    Some(ratio) if ratio >= config.min_profit_ratio => {
                        let note = format!(
                            "售价 {} - 货源 {}（利润率 {:.0}%）",
                            candidate.sell_price,
                            quote.lowest_price,
                            ratio * 100.0
                        );
                        (deps.store)(&candidate.raw, &note)?;
                        summary.accepted += 1;
                    }
                    // 边界案例交给 AI 复核；明确不达标直接拒绝。
                    Some(ratio) if ratio >= config.min_profit_ratio * 0.5 => {
                        let candidate_json = serde_json::to_string(&candidate.raw)
                            .map_err(|error| error.to_string())?;
                        let quote_json =
                            serde_json::to_string(&quote).map_err(|error| error.to_string())?;
                        let raw = (deps.call_ai)(build_verdict_prompt(
                            &config.criteria,
                            &candidate_json,
                            &quote_json,
                        ))?;
                        match parse_verdict(&raw) {
                            Ok(verdict) if verdict.keep => {
                                (deps.store)(&candidate.raw, &verdict.reason)?;
                                summary.accepted += 1;
                            }
                            _ => summary.rejected += 1,
                        }
                    }
                    _ => summary.rejected += 1,
                }
            }
        }

        report.total_accepted += summary.accepted;
        report.total_rejected += summary.rejected;
        report.rounds.push(summary);

        // 连续两轮无入库则提前收敛；否则让 AI 基于历史修正方向。
        let last = report.rounds.last().expect("round pushed");
        if last.accepted == 0 && last.xianyu_scanned > 0 {
            stale_rounds += 1;
            if stale_rounds >= 2 {
                report.stop_reason = "no_new_direction".into();
                return Ok(report);
            }
        } else {
            stale_rounds = 0;
        }

        let raw = (deps.call_ai)(build_refine_prompt(&config.criteria, &report))?;
        keywords = parse_keywords(&raw)?;
        dedup_keywords(&mut keywords, &report);
        if keywords.is_empty() {
            report.stop_reason = "no_new_direction".into();
            return Ok(report);
        }
    }

    report.stop_reason = "budget_exhausted".into();
    Ok(report)
}

/// 新关键词去掉历史已用过的方向。
fn dedup_keywords(keywords: &mut Vec<String>, report: &DiscoveryReport) {
    let used: HashSet<&str> = report
        .rounds
        .iter()
        .flat_map(|round| round.keywords.iter())
        .map(String::as_str)
        .collect();
    keywords.retain(|keyword| !used.contains(keyword.as_str()));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dedups_against_history() {
        let report = DiscoveryReport {
            rounds: vec![DiscoveryRoundSummary {
                round: 1,
                keywords: vec!["旧词".into()],
                ..Default::default()
            }],
            ..Default::default()
        };
        let mut keywords = vec!["旧词".to_string(), "新词".to_string()];
        dedup_keywords(&mut keywords, &report);
        assert_eq!(keywords, vec!["新词".to_string()]);
    }
}
