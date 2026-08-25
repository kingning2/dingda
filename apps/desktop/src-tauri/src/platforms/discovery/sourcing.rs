//! 供给侧 — 1688 同款比价，取最低供货价。
//!
//! 搜索走 sidecar 的 `channels/ali1688/search`（Playwright 抓取，
//! GBK 编码关键词由 Python 侧处理）；此处只做结果解析与最低价提取。

use serde_json::Value;

/// 1688 比价结果。
#[derive(Debug, Clone, serde::Serialize)]
pub struct SourceQuote {
    /// 最低供货价（元）。
    pub lowest_price: f64,
    /// 对应货源标题（供人工核对是否同款）。
    pub source_title: String,
    /// 原始报价条数。
    pub quotes: usize,
}

/// 从 1688 搜索结果列表中提取最低供货价。
///
/// 字段名以 sidecar `channels/ali1688/search/fetch.py::offers` 的实际返回为准，
/// 接入时对齐（TODO：确认字段映射）。
pub fn extract_lowest_quote(offers: &[Value]) -> Option<SourceQuote> {
    let mut best: Option<(f64, String)> = None;
    for offer in offers {
        let Some(price) = offer.get("price").and_then(Value::as_f64) else {
            continue;
        };
        let title = offer
            .get("title")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        if best.as_ref().is_none_or(|(lowest, _)| price < *lowest) {
            best = Some((price, title));
        }
    }
    let (lowest_price, source_title) = best?;
    Some(SourceQuote {
        lowest_price,
        source_title,
        quotes: offers.len(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn picks_lowest_price() {
        let offers = vec![
            json!({"title": "货源A", "price": 42.0}),
            json!({"title": "货源B", "price": 35.5}),
            json!({"title": "缺价"}),
        ];
        let quote = extract_lowest_quote(&offers).expect("quote");
        assert_eq!(quote.lowest_price, 35.5);
        assert_eq!(quote.source_title, "货源B");
        assert_eq!(quote.quotes, 3);
    }

    #[test]
    fn empty_offers_is_none() {
        assert!(extract_lowest_quote(&[]).is_none());
    }
}
