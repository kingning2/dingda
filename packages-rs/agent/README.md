# agent

面向 **设置页 / IPC** 的薄层：把 `runtime` 的探测结果收成前端列表形状。  
不是 Python 产品 Agent（那个在 `packages-py/agent/src/agent/`）。不要在这里 spawn CLI。

```text
commands/agent_runtime.rs
        → catalog / probe / discover
                → runtime::registry / detection / resolution
```

## 本目录文件

### `mod.rs`

导出 `catalog`、`discover`、`probe`、`registry`。

### `registry.rs`

- `AGENT_REGISTRY` — 就是 `RUNTIME_REGISTRY` 的别名，避免前端「Agent」和内部「Runtime」两套表
- `AgentListResponse` / `AgentRuntimeCatalogItem` / `AgentRuntimeStatusView` — 设置页卡片 DTO（camelCase）
- `find_agent` — 转调 `find_runtime`

改 CLI 列表请改 `runtime/registry.rs`，不要在这里再抄一份 id。

### `catalog.rs`

`list_agent_runtimes()`：遍历 registry，用 `discover_agent_with_source` 填「已就绪/未安装」、command 路径、MCP 注入标记。给 `list_agent_runtimes_command`。不做 `--version`（那是 probe）。

### `discover.rs`

`discover_agent` / `discover_agent_with_source`：委托 `runtime::resolve_executable`。保证「列表里看到的路径 = 真正启动的路径」。

### `probe.rs`

- `probe_agent` / `probe_agent_by_id` — `detect_runtime` + `discover_models`，返回版本、是否登录、模型列表
- `login_agent_by_id` — 按 definition 的 login 能力拉起 CLI 登录（能 login 的才有按钮）

异步，由 command 直接 `await`。

## 子目录

无。实现细节：[../runtime/README.md](../runtime/README.md)。
