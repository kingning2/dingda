# runtime/defs

每个文件一个 CLI 插头：导出 `pub const FOO: RuntimeDefinition`。  
模型发现组合 [../model_discover/README.md](../model_discover/README.md)。启动参数在 Python `agent/runtimes`，壳只负责探测 / 下载 / catalog。

新增：本目录加 `<id>.rs` → `mod.rs` `pub use` → [../registry.rs](../registry.rs) 登记。不要在业务里 match id。

产品当前对外：`opencode` / `claude` / `codex`。

## 本目录文件

### `base.rs`

Runtime 插头抽象方法（实现在 `RuntimeDefinition` 上）：

- `supports_managed_download` / `managed_dir` / `managed_binary_path`
- `resolve_managed` — 探测托管目录
- `download_managed` — 统一下载 / 解压 / 落盘

各插头只填 `managed_download: Some(ManagedDownloadSpec { ... })`，不要复制下载代码。

### `mod.rs`

`mod` + `pub use` 所有常量。registry 从这里 import，不要从单个文件散引。

### `codex.rs`

`CODEX`，id `codex`。`external_mcp_injection: Some("codex-mcp")`。模型：`login status` 成功则 `debug models`，否则静态列表。  
`managed_download`：GitHub latest（Win 裸 `.exe`，macOS/Linux `.tar.gz`）。

### `claude.rs`

`CLAUDE`，id `claude`。注入标记 `claude-mcp-json`（cwd `.mcp.json`）。  
`managed_download`：`downloads.claude.ai` + `version_file=latest` → `{ver}/{platform}/claude[.exe]`。

### `opencode.rs`

`OPENCODE`，id `opencode`。注入 `opencode-env-content`。  
`managed_download` 指向 GitHub latest；实际下载由 `base.rs` 执行。
