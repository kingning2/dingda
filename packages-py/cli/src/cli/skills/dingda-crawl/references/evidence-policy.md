# Evidence Policy

## Source priority

| 来源 | 主要用途 | 不能替代 |
|------|----------|----------|
| 闲鱼 | 真实货盘、二手价格、卖家描述和留言 | 小红书内容判断 |
| 小红书 | 内容风向、需求场景、用户表达 | 闲鱼真实成交货盘 |
| 1688 | 货源、同款和拿货价 | 来源商品硬约束 |

## Search discipline

- 闲鱼建样本池时至少换词执行三轮，目标累计约 100 条去重样本。
- 小红书通常执行 1 到 3 轮，视频笔记跳过详情。
- 每一轮都记录平台、查询词、返回数量和新增去重数量。
- 单次列表结果不能直接支撑价格或选品结论。

## Detail discipline

闲鱼详情优先读取：

- `title`
- `price`
- `desc`
- `want_count`
- `seller_nick`
- `comments`

小红书图文详情优先读取 `content_text`，其次读取 `desc` 和 `ocr_text`。

## Price compare discipline

进入 1688 比价前必须满足：

1. 有合法 `source_card`。
2. 来源商品至少有 `platform`、`item_id` 或 `url`、`title` 和 `image_url`。
3. 至少执行三轮不同策略。
4. 每轮记录查询词、策略、返回数和新增候选。
5. 所有候选按 `item_id` 去重。
6. 候选交给 `dingda-offer-verification` 后才允许给最终推荐。

## Evidence failures

- 登录失效：调用 `login`，等待扫码，然后重试。
- 页面结构变化：如实报告工具错误，不凭页面猜测字段。
- 视频笔记：标记为未读取详情，不要说已经分析。
- 运费、SKU、MOQ 或商家字段缺失：写 `unknown` 或给出条件区间。
- 样本不足：明确写出已完成轮次和缺少的证据，不强行推荐。

## Output rules

最终回答只包含本次实际执行的证据。每个商品结论至少关联一个 `item_id` 或 URL。不要把不同平台的证据混成一个来源，也不要声称已做全量抓取。
