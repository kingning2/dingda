# domains/watch

商品监控：把一批商品长期盯着，看它们**卖不卖得掉**、**降没降价**。

回答两个问题：

1. 这个商品过几天还在卖吗？（还在卖 = 需求可能不旺；卖掉了 = 需求被验证）
2. 卖家降过价吗？降了多少？

不负责搜品（那是 crawler + tools），不负责通知出口（本产品暂无外部通知）。

## 本目录文件

### `base.py`

取数**插座**：`ProductSnapshot`（归一后的取数结果）+ `ProductFetcher`（协议）。

`domains` 不依赖 `tools`，而 `api` 是唯一同时依赖两者的层，所以「取一次详情」这件事
由 `api.watch_feed.fetch_product` 实现插头，挂载时注入。

### `poller.py`

`poll_target(target, fetcher=…, next_poll_at=…)`：轮询一条商品——取详情、把价格文本收敛成
数字（`parse_price`，支持 `¥1,234.5` 与 `¥1.2万`）、判定售出态，落一个价格点并推进快照。

`resolve_target_cookie`：优先用目标指定的 `account_id`，否则取该平台第一个 `auth_valid` 的账号。

**落点纪律**：抓取失败（风控 / 网络 / 登录失效）**不落点**，只累计 `fail_count`；
但 `crawler.not_found` 要落点并记 `sold_state=gone`——「详情取不到」正是要观察的信号。

### `insight.py`

`derive_changes(points)`：按时间正序比相邻两点，产出降价 / 涨价 / 售出 / 下架 / 重新在售事件
（`WatchChange`）。纯函数，不碰库，单测直接喂点序列。

### `service.py`

`add_targets` / `list_views` / `get_detail` / `patch_target` / `remove_target` / `summarize`。

涨跌口径（`price_drop` = 首价 − 现价，正数即降价）与 `watched_hours` 在这里算完，
API 层只做序列化。`clamp_interval` 把间隔夹在 1 分钟 ~ 7 天。

### `scheduler.py`

`schedule_watch_scheduler(fetcher)`：由 `api.boot.warmup` 在 `init_db` 之后挂上（幂等）。

- 每 60 秒跑一轮，每轮最多 25 条
- **串行 + 摊开**：两条之间等 `最小间隔 / 活跃条数`，夹在 20s ~ 30min。
  活跃 N 条、间隔 T 时，请求速率约 N/T，不会集中爆发
- 失败退避：第 n 次失败后等 `interval × 2^(n-1)`，上限 24 小时
- 商品售出/下架后**不停止**，降到 24 小时一次慢速确认，既省配额又能捕捉重新上架
- 新加入的目标 `next_poll_at` 即当前时刻，所以加完会立刻排进下一轮，不用等一个完整间隔
- `poll_targets_now(fetcher, target_ids=…)` 给手动触发接口用，不受每轮上限约束

### `__init__.py`

包标记。

## 子目录

无。表结构：[infrastructure/db](../../../../infrastructure/src/infrastructure/db/README.md)。
取数插头：[api/watch_feed.py](../../../../api/src/api/README.md)。
