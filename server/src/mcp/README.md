# mcp

把 [../tools/README.md](../tools/README.md) 暴露成 **stdio MCP**（命令 `dingda-mcp`）。当前工具与 registry 一致：`search` / `product` / `compare` / `preview`。

大 JSON 出口经 [`agent/core/compress.py`](../agent/core/compress.py)（Headroom）压缩后再回给 CLI。

桌面壳 / Python Runtime：`uv run --directory server dingda-mcp`。  
**产品搜品不走 MCP**，走产品 Agent 进程内 `call_tool`。

## 本目录文件

### `server.py`

`create_mcp_server()` + `main()` stdio 入口。

### `register.py`

`register_internal_tools(mcp)`：遍历 `list_tools()` 挂到 FastMCP；返回前 `compress_tool_payload`。

### `catalog.py`

`list_builtin_mcp_servers()`：设置页展示用。

### `__init__.py`

包标记。
