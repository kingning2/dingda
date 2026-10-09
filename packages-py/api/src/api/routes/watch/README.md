# watch/

`/v1/watch`：商品监控——把一批商品长期盯着，看卖不卖得掉、降没降价。

- `add_targets.py` — `POST /targets` 批量加入监控（同 `platform+item_id` 幂等）
- `list_targets.py` — `GET /targets` 列表，带涨跌额与售出态
- `get_target.py` — `GET /targets/{target_id}` 单条：完整价格历史点 + 变更事件
- `patch_target.py` — `PATCH /targets/{target_id}` 改状态（active/paused/archived）或轮询间隔
- `delete_target.py` — `DELETE /targets/{target_id}` 彻底移除（含历史）；想留历史改用 PATCH 归档
- `summary.py` — `GET /summary` 概览：多少还在卖、多少卖掉了、多少降价了
- `poll.py` — `POST /poll` 立刻轮询几条（手动验证用，最多 5 条）

设计说明：
- `_dto.py` 放请求 / 响应模型与「服务层视图 → HTTP DTO」映射；涨跌口径在
  [watch 域](../../../../../domains/src/domains/watch/README.md)，本层只搬运字段
- 取数插头 `fetch_product` 在 [../../lib/watch_feed.py](../../lib/watch_feed.py)
- 后台定时轮询由 [boot/warmup.py](../../boot/warmup.py) 挂 `domains.watch.scheduler`，不在本层
