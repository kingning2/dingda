# runtime/defs

每个文件一个 CLI 插头：导出 `pub const FOO: RuntimeDefinition`。  
模型发现组合 [../model_discover/README.md](../model_discover/README.md)。启动参数在 Python `agent/runtimes`，壳只负责探测 / 下载 / catalog。

新增：本目录加 `<id>.rs` → `mod.rs` `pub use` → [../registry.rs](../registry.rs) 登记。不要在业务里 match id。

产品当前对外：`opencode` / `claude` / `codex`。

## 本目录文件

### `base.rs`

Runtime 插头抽象方法（实现在 `RuntimeDefinition` 上），只管「装在哪、怎么认出来」：

- `supports_managed_download` / `managed_dir` / `managed_binary_path`
- `resolve_managed` — 探测托管目录

托管下载 / 安装见 [../install.rs](../install.rs)。

各插头只填 `managed_download: Some(ManagedDownloadSpec { ... })`，不要复制下载代码。

## 插头字段

- `auth: Option<RuntimeAuth>` — 鉴权契约。`probe_args` 跑 CLI 子命令；
  `parse`（`AuthParse::ExitCode` / `JsonLoggedIn` / `CredentialCount`）决定怎么判；
  `login_args` 为空表示不能由平台触发登录，`login_message` 是登录后给前端的提示。
  判定逻辑在 [../detection.rs](../detection.rs) 的 `probe_auth`，登录在 [../../agent/probe.rs](../../agent/probe.rs) 的 `login_agent_by_id`。
- `can_login()` — `auth` 存在且 `login_args` 非空。

`can_login` / `parse` 这类判断都读字段，不要在业务代码里 match `id`。

### `mod.rs`

`mod` + `pub use` 所有常量。registry 从这里 import，不要从单个文件散引。

### `codex.rs`

`CODEX`，id `codex`。`external_mcp_injection: Some("codex-mcp")`。模型：`login status` 成功则 `debug models`，否则静态列表。  
鉴权：`auth = RuntimeAuth { probe_args: ["login","status"], parse: ExitCode, login_args: ["login"] }`。  
`managed_download`：GitHub latest（Win 裸 `.exe`，macOS/Linux `.tar.gz`）。

### `claude.rs`

`CLAUDE`，id `claude`。注入标记 `claude-mcp-json`（cwd `.mcp.json`）。  
模型：先拉 models.dev 的 anthropic 目录，失败回落静态 5 项（见 `../model_discover/modelsdev.rs`）。  
鉴权：`probe_args: ["auth","status"], parse: JsonLoggedIn, login_args: ["auth","login"]`。  
`managed_download`：`downloads.claude.ai` + `version_file=latest` → `{ver}/{platform}/claude[.exe]`。

### `opencode.rs`

`OPENCODE`，id `opencode`。注入 `opencode-env-content`。  
鉴权：`probe_args: ["auth","list"], parse: CredentialCount, login_args: ["auth","login"]`。  
`managed_download` 指向 GitHub latest；实际下载由 [../install.rs](../install.rs) 执行。
