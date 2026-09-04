# tools

MCP 与产品 Agent **共用**的选品能力。每个 Tool 一个文件（契约 + `run_*`），`registry.py` 负责注册。

不要在 MCP / Agent 里复制命令。不要在 Tool 里 `import playwright` / `camoufox`。

## 本目录文件

| 文件 | 职责 |
|------|------|
| `search.py` | 关键词 / 图 / 链接搜品（含 ali1688） |
| `product.py` | 单品详情（xianyu / xiaohongshu） |
| `compare.py` | 1688 同款比价 |
| `registry.py` | `list_tools` / `get_tool` / `call_tool` |
| `__init__.py` | 包导出 |

新增 Tool：在本目录加 `<name>.py`，再在 `registry.py` 的 `_TOOLS` 挂一条。
