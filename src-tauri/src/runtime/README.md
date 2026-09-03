# Runtime

多 CLI Agent 的统一运行时层。负责**发现可执行文件 → 探测状态 → 构建启动参数 → 拉起进程 → 解析 stdout → 推送 `AgentEvent`**。

不负责下载/安装 CLI；`agent/` 模块是面向 Tauri IPC 的薄适配层，核心逻辑都在本目录。

## 数据流

```
RuntimeDefinition (defs/)
        │
        ├─► resolution::resolve_executable()     找二进制
        ├─► detection::detect_runtime()          版本 / 认证
        ├─► model_discover (defs.discover_models) 可用模型列表
        │
        └─► invocation::build_invocation()       拼启动参数
                    │
                    ▼
            process::spawn_process()             拉起子进程
                    │
                    ▼
            parsers::*::feed(line)               stdout 行 → AgentEvent
                    │
                    ▼
            manager::launch_with_app()           Tauri emit("agent-event")
```

**设计原则**

- Detection 与 Launch 共用 `resolve_executable()`，保证「探测到的路径 = 实际启动的路径」。
- 核心逻辑不出现 `if runtime == "codex"` 式分支；按 CLI 差异写在 `defs/<name>.rs` 与对应 parser。
- 新增 CLI：加一个 definition 文件 +（如需）parser + 在 `registry.rs` 注册。

---

## 顶层文件

| 文件 | 职责 |
|------|------|
| `mod.rs` | 模块入口；对外 re-export 常用类型与 `RuntimeManager`。 |
| `types.rs` | 核心类型：`RuntimeDefinition`、`RuntimeInvocation`、`RuntimeDetection`、`RuntimeModel`、`AgentEvent` 相关契约、`StreamFormat`、函数指针类型 `DiscoverModelsFn`。 |
| `registry.rs` | `RUNTIME_REGISTRY` 静态表与 `find_runtime(id)` 查找。 |
| `resolution.rs` | `resolve_executable()`：Configured 环境变量 → 动态 PATH（含 Windows 注册表）→ 已知安装目录。带 shell 解析缓存。 |
| `detection.rs` | `detect_runtime()`：在 resolution 基础上跑 `--version`、登录/认证探测，返回 `RuntimeDetection`。 |
| `invocation.rs` | `build_invocation()` / `invocation_context()`：把 definition + prompt/cwd/model 合成 `RuntimeInvocation`；按 `external_mcp_injection` 注入 MCP（如 Codex `-c mcp_servers...`）。 |
| `process.rs` | `spawn_process()` 启动子进程；`read_stdout_lines()` 按行读 stdout（stderr 暂未全量解析）。 |
| `runs.rs` | 进程注册表：`register` / `cancel` / `unregister`，支持按 `run_id` 杀进程。 |
| `event.rs` | `AgentEvent` 枚举、`AgentEventEnvelope`（带 `run_id`）、`StreamParser` trait。 |
| `manager.rs` | `RuntimeManager`：编排 launch 全流程（emit `RunStarted` → spawn → parse → `RunCompleted`）；`cancel_run`。 |

---

## `defs/` — 每个 CLI 一份定义

每个文件导出一个 `RuntimeDefinition` 常量（如 `CODEX`、`OPENCODE`），集中声明：

- 二进制名、`DINGDA_*_PATH` 环境变量、文档链接
- `stream_format`（决定用哪个 parser）
- `capabilities`（是否支持登录、stdin 传 prompt 等）
- `build_args` — 启动参数构建函数
- `discover_models` — 模型列表发现函数
- 可选：`validate_executable`、`auth_probe_args`

| 文件 | CLI |
|------|-----|
| `codex.rs` | OpenAI Codex |
| `claude.rs` | Anthropic Claude Code |
| `opencode.rs` | OpenCode |
| `cursor.rs` | Cursor Agent (`cursor-agent`) |
| `mimo.rs` | Mimo |
| `deepseek.rs` | DeepSeek / CodeWhale |
| `deepseek_harness.rs` | DeepSeek Harness (`dsh`) |
| `qwen.rs` | Qwen |
| `qoder.rs` | Qoder |
| `grok.rs` | Grok Build |
| `pi.rs` | Pi |
| `trae.rs` | Trae CLI |
| `codebuddy.rs` | CodeBuddy |

**共享子模块**

| 文件 | 职责 |
|------|------|
| `build_args.rs` | 各 CLI 的 `build_args` 实现（`codex_build_args`、`opencode_build_args` 等）。 |
| `validate.rs` | 可选的可执行文件校验（如 DSH probe）。 |
| `mod.rs` | 汇总导出所有 `RuntimeDefinition` 常量。 |

---

## `model_discover/` — 模型列表发现

Probe 阶段调用 `definition.discover_models(binary)` 获取可选模型。

| 文件 | 职责 |
|------|------|
| `mod.rs` | 模块入口，re-export 公共 API。 |
| `common.rs` | `run_command`、stdout 解析器（OpenCode / Cursor / Pi / Codex debug JSON 等）、`static_models` 辅助。 |
| `acp.rs` | 通过 ACP JSON-RPC 会话发现模型（Qoder、Trae、Mimo、Grok 等）。 |
| `dsh.rs` | DeepSeek Harness `--list-models` JSONL 解析。 |

具体策略写在各 `defs/<name>.rs` 的 `discover_models` 中，可组合上述 helper。

---

## `mcp/` — 外部 Agent MCP 注入

启动 CLI 时**进程级**注入 MCP，不修改用户全局配置（如 `~/.codex/config.toml`）。

| 模式 | Agent | 机制 |
|------|-------|------|
| `codex-mcp` | Codex | `codex -c 'mcp_servers.goofish={...}' exec ...`，拉起 `uv run dingda-mcp` |
| `opencode-env-content` | OpenCode | `OPENCODE_CONFIG_CONTENT` 内联 JSON，注册 local MCP `goofish` |

---

## `parsers/` — stdout 流解析

把 CLI 原始输出行转为 `AgentEvent`。由 `StreamFormat` + `runtime_id` 在 `parsers/mod.rs::create_parser()` 分发。

| 文件 | 职责 |
|------|------|
| `mod.rs` | `create_parser()` 工厂；`parse_json_line()` 工具。 |
| `codex.rs` | Codex / Cursor / Mimo 的 JSON 流（`response.output_text.delta` 等）。 |
| `opencode.rs` | OpenCode 事件流（`text`、`part_delta`、`tool_use` 等）。 |
| `claude.rs` | Claude / CodeBuddy / Qoder 的 stream-json（`content_block_delta`、`tool_use`）。 |
| `json_event.rs` | 通用 JSON 行事件解析（ACP、Pi、DSH 等 fallback）。 |
| `plain.rs` | 纯文本 stdout → `TextDelta`。 |

---

## 与 `agent/` 的关系

| `agent/` | `runtime/` |
|----------|------------|
| `catalog` — IPC 列表响应组装 | `registry` + `detection` + `resolution` |
| `probe` — 调用 `detect_runtime` + `discover_models` | 提供探测与模型发现实现 |
| `discover` — 薄封装 `resolve_executable` | `resolution` |
| Tauri commands (`commands/agent_runtime.rs`) | `RuntimeManager::launch_with_app` |

前端通过 `agent-event` Tauri 事件消费 `AgentEvent`，不直接接触本模块。

---

## 新增 CLI 检查清单

1. 在 `defs/<id>.rs` 新建 `RuntimeDefinition`（含 `build_args`、`discover_models`）。
2. 在 `defs/mod.rs` 注册 `mod` 与 `pub use`。
3. 在 `registry.rs` 的 `RUNTIME_REGISTRY` 加入常量。
4. 若 stdout 格式特殊，在 `parsers/` 增加 parser 并在 `create_parser()` 挂接。
5. 前端 composer / agent-runtime 契约补充该 `id`（如有需要）。
