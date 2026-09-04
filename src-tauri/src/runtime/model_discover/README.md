# runtime/model_discover

Probe 阶段拉「可选模型」的共用实现。各 `defs/<id>.rs` 的 `discover_models` 调用这里，不要每个 CLI 复制一遍 `Command::output`。

失败时 defs 里通常回退 `static_models`，不要在这里 panic。

## 本目录文件

### `mod.rs`

re-export `run_command`、各 parse_*、`discover_acp_models`、`discover_dsh_models`。

### `common.rs`

- `run_command(binary, args)` — 要 stdout
- `static_models(&[("id","label")])` — 登录失败时的硬编码列表
- `parse_codex_debug_models` / `parse_opencode_models` / `parse_cursor_models` / `parse_pi_models`
- `parse_id_label_lines` / `parse_plain_id_lines` — 行格式各异时的兜底

### `acp.rs`

`AcpDiscoveryConfig` + `discover_acp_models`：拉起 ACP stdio，JSON-RPC `session/new` 里抠模型。Grok / Trae / Qoder / Mimo 等走这条。

### `dsh.rs`

`discover_dsh_models`：`dsh --list-models` 一类 JSONL。只给 DeepSeek Harness。

## 子目录

无。谁调用：[../defs/README.md](../defs/README.md)。
