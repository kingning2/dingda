# runtime/model_discover

从各 CLI 拉可用模型列表。defs 的 `discover_models` 调这里的解析 / 探测函数。

## 本目录文件

### `mod.rs`

re-export `run_command`、`parse_codex_debug_models`、`parse_opencode_models`、`static_models`、`fetch_models_dev_anthropic`。

### `common.rs`

- `run_command` — 异步跑 CLI 取 stdout
- `static_models` — 静态 id/label 列表
- `parse_codex_debug_models` / `parse_opencode_models` — 各 CLI 帮助或探测输出的解析

### `modelsdev.rs`

models.dev 公共目录（`https://models.dev/api.json`）。`claude` 没有列模型的子命令，用它取 anthropic 目录；
`fetch_models_dev_anthropic` 拉不到就返回空，由 `defs/claude.rs` 回落静态列表。HTTP 复用 `defs/base.rs::fetch_text`。
