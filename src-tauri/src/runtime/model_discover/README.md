# runtime/model_discover

从各 CLI 拉可用模型列表。defs 的 `discover_models` 调这里的解析 / 探测函数。

## 本目录文件

### `mod.rs`

re-export `run_command`、`parse_codex_debug_models`、`parse_opencode_models`、`static_models`。

### `common.rs`

- `run_command` — 异步跑 CLI 取 stdout
- `static_models` — 静态 id/label 列表
- `parse_codex_debug_models` / `parse_opencode_models` — 产品三家用到的解析
