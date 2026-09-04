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

`agent_works` 对话快照：`get_work` / `upsert_work`，整份 detail JSON。给 `/v1/agent/works/{work_id}` 用。

### `__init__.py`

包标记。

## 子目录

无。
