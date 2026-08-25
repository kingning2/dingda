//! 跨平台比价选品 — 闲鱼（需求侧）× 1688（供给侧）套利发现循环。
//!
//! 流程：
//!
//! ```text
//! 生成/修正关键词(LLM)
//!   → 闲鱼搜索，按「想要人数」过滤出强需求商品
//!   → 每个候选去 1688 搜同款取最低供货价
//!   → 本地算利润率，达标(或 AI 复核)→ 入库
//!   → 基于本轮结果修正关键词，循环直到预算耗尽或无新方向
//! ```
//!
//! 与 [`super::xianyu::monitor`]（单站固定关键词监控）互补：discovery 是
//! 平台无关的双站编排，搜索能力复用 sidecar 的 `channels/xianyu/search`
//! 与 `channels/ali1688/search`。
//!
//! 结构：
//! - [`keywords`]  — 关键词生成与基于结果的自我修正（LLM）
//! - [`demand`]    — 闲鱼需求侧：搜索 + 想要人数门槛过滤
//! - [`sourcing`]  — 1688 供给侧：同款比价取最低供货价
//! - [`evaluate`]  — 利润判定（本地利润率 + LLM 结构化复核）
//! - [`runner`]    — 循环编排（预算、跨轮去重、检查点）

pub mod demand;
pub mod evaluate;
pub mod keywords;
pub mod runner;
pub mod sourcing;

use serde::{Deserialize, Serialize};

/// 发现循环配置。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveryConfig {
    /// 种子关键词（首轮闲鱼搜索起点）。
    pub seed_keywords: Vec<String>,
    /// 选品标准（自然语言，喂给 AI 修正与复核）。
    pub criteria: String,
    /// 最大轮数。
    pub max_rounds: u32,
    /// 每个关键词最大搜索条数。
    pub max_results_per_keyword: i64,
    /// 需求门槛：闲鱼商品「想要人数」不低于该值才进入比价。
    pub min_wanters: u32,
    /// 利润率门槛：`(售价 - 供货价) / 供货价` 不低于该值才入库。
    pub min_profit_ratio: f64,
}

impl Default for DiscoveryConfig {
    fn default() -> Self {
        Self {
            seed_keywords: Vec::new(),
            criteria: String::new(),
            max_rounds: 5,
            max_results_per_keyword: 20,
            min_wanters: 10,
            min_profit_ratio: 0.3,
        }
    }
}

/// 单轮发现摘要。
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DiscoveryRoundSummary {
    pub round: u32,
    pub keywords: Vec<String>,
    pub xianyu_scanned: usize,
    pub demand_passed: usize,
    pub sourced: usize,
    pub accepted: usize,
    pub rejected: usize,
}

/// 整次发现的最终报告（可落库作为检查点）。
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DiscoveryReport {
    pub rounds: Vec<DiscoveryRoundSummary>,
    pub total_accepted: usize,
    pub total_rejected: usize,
    /// 终止原因：budget_exhausted / no_new_direction / completed。
    pub stop_reason: String,
}

/// 跨轮已见商品 ID 集合（序列化以支持断点续跑）。
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SeenItems(pub std::collections::HashSet<String>);

/// 纯本地利润率计算 — 达标与否不依赖 AI，AI 只做边界案例复核。
pub fn profit_ratio(sell_price: f64, cost_price: f64) -> Option<f64> {
    if cost_price <= 0.0 || sell_price < 0.0 {
        return None;
    }
    Some((sell_price - cost_price) / cost_price)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn computes_profit_ratio() {
        let ratio = profit_ratio(130.0, 100.0).expect("ratio");
        assert!((ratio - 0.3).abs() < f64::EPSILON);
        assert!(profit_ratio(100.0, 0.0).is_none());
    }
}
