# mcp

把 [../tools/README.md](../tools/README.md) 暴露成 **stdio MCP**（命令 `dingda-mcp`）。当前工具与 registry 一致：`search` / `product` / `compare`。

桌面壳：`uv run --directory server dingda-mcp`。

## 本目录文件

### `server.py`

`create_mcp_server()` + `main()` stdio 入口。

### `register.py`

`register_internal_tools(mcp)`：遍历 `list_tools()` 挂到 FastMCP。

### `catalog.py`

`list_builtin_mcp_servers()`：设置页展示用。

### `__init__.py`

包标记。
