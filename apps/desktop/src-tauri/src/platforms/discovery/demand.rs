//! 需求侧 — 闲鱼搜索结果按「想要人数」过滤出强需求商品。
//!
//! 搜索走 sidecar 的 `channels/xianyu/search`（复用
//! [`super::super::xianyu::monitor::search`] 的通道），此处只做纯数据
//! 过滤与字段提取，便于单测。

use serde_json::Value;

/// 通过需求门槛的闲鱼候选商品。
#[derive(Debug, Clone)]
pub struct DemandCandidate {
    /// 闲鱼商品 ID（跨轮去重键）。
    pub item_id: String,
    pub title: String,
    pub sell_price: f64,
    /// 想要人数（需求强度信号）。
    pub wanters: u32,
    /// 原始商品 JSON（透传给比价与入库）。
    pub raw: Value,
}

/// 从闲鱼商品 JSON 提取候选；不满足门槛返回 `None`。
///
/// 字段名以 sidecar `channels/xianyu/search/fetch.py` 的实际返回为准，
/// 接入时对齐（TODO：确认字段映射）。
pub fn filter_candidate(item: &Value, min_wanters: u32) -> Option<DemandCandidate> {
    let item_id = item
        .get("id")
        .or_else(|| item.get("item_id"))
        .and_then(Value::as_str)?
        .to_string();
    let title = item
        .get("title")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let sell_price = item.get("price").and_then(Value::as_f64)?;
    let wanters = item
        .get("wanters")
        .or_else(|| item.get("want_count"))
        .and_then(Value::as_u64)? as u32;
    if wanters < min_wanters {
        return None;
    }
    Some(DemandCandidate {
        item_id,
        title,
        sell_price,
        wanters,
        raw: item.clone(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn passes_when_wanters_meet_threshold() {
        let item = json!({"id": "a1", "title": "耳机", "price": 88.0, "wanters": 15});
        let candidate = filter_candidate(&item, 10).expect("candidate");
        assert_eq!(candidate.item_id, "a1");
        assert_eq!(candidate.wanters, 15);
    }

    #[test]
    fn rejects_below_threshold_or_missing_price() {
        let weak = json!({"id": "a2", "title": "杂项", "price": 10.0, "wanters": 3});
        assert!(filter_candidate(&weak, 10).is_none());
        let no_price = json!({"id": "a3", "title": "无价", "wanters": 99});
        assert!(filter_candidate(&no_price, 10).is_none());
    }
}
