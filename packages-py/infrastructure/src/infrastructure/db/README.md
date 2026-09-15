# infrastructure/db

账号等产品表。路径默认 `Path.home() / ".dingda" / "v2" / "dingda.db"`。测试可 `set_db_path`。

闲鱼 token 缓存、limiter 状态是 Channel 自己的 JSON 文件，不在这张库。

## 本目录文件

### `session.py`

`data_dir` / `db_path` / `set_db_path`。`init_db` 调 accounts `ensure_schema`。lifespan 与 warmup 都会碰到。

### `schema.py`

`CREATE TABLE accounts` / `app_settings` / `agent_works`，以及 accounts 的 ALTER 列 SQL。改表先改这里再改对应 repo。

### `accounts.py`

`AccountRow` dataclass；`ensure_schema`、`list_accounts`、`get_account`、`upsert_account`、`set_connected`、删除。只做 SQL，不做 HTTP 文案（文案在 `domains.account.session`）。

### `settings.py`

`app_settings` KV：`get_setting` / `set_setting`，以及 `get_default_agent_id` / `set_default_agent_id` / `get_default_models` / `set_default_model`。给 `/v1/agent/*` 偏好用。

### `agent_works.py`

`agent_works` 对话快照：`get_work` / `list_works` / `upsert_work`。列表给 `GET /v1/agent/works`（首页最近项目），详情给 `/v1/agent/works/{work_id}`。

### `watch.py`

商品监控两张表：`watch_targets`（被监控商品的最新快照：首价/现价/最低价/最高价/售出态/下次轮询时间）与 `watch_points`（只增不改的价格历史点）。

- `upsert_target` 加入监控（按 `(platform, item_id)` 去重；原行若是 paused/archived 顺手恢复 active）
- `list_targets` / `get_target` / `list_due_targets` / `count_active` 给列表接口与调度器
- `set_target_state` / `set_poll_interval` / `set_next_poll_at` / `delete_target`（删除会连带清掉该目标全部历史点）
- `save_poll_snapshot` 轮询成功后写回快照并推进首价/最低/最高聚合（`title` 只在为空时回填）；`record_poll_failure` 只累计失败次数与错误
- `add_point` / `list_points` 价格历史读写

`state` 本层只当落库值筛选（`TARGET_ACTIVE`），语义与取值词表在 `contracts.watch.WatchState`。

只做 SQL 与聚合，不做轮询、不做价格文本解析、不做结论推导（那三件事在 `domains.watch`）。

### `__init__.py`

包标记。

## 子目录

无。
