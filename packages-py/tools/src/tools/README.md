# tools

产品 Agent 与 CLI skill **共用**的选品能力。每个 Tool 一个文件（契约 + `run_*`），`registry.py` 负责注册。

不要在 CLI skill / Agent 里复制命令。不要在 Tool 里 `import playwright` / `camoufox`。

## 本目录文件

| 文件 | 职责 |
|------|------|
| `search.py` | 关键词 / 图 / 链接搜品（含 ali1688） |
| `product.py` | 单品详情（xianyu / xiaohongshu） |
| `compare.py` | 1688 多轮同款比价（来源商品 + 价格/销量/商家依据） |
| `preview.py` | 打开任意 URL，直播截图给前端预览 |
| `login.py` | 平台扫码登录（阻塞等用户扫码） |
| `account_cookie.py` | 爬虫 / 预览用账号 Cookie 与会话解析 |
| `recovery.py` | 抓取会话恢复（登录失效 → 扫码 → 重试） |
| `live_push.py` | 在 `tools.cli` 子进程里把截图 POST 回 Server live-frame |
| `cli.py` | 通用命令行入口：按 registry 的 Input Schema 调工具并输出 JSON |
| `validate.py` | **内部工具**：在修复现场页面上试跑候选选择器（只给修复子 agent） |
| `validate_cli.py` | 同上的命令行形态：`python -m tools.validate_cli --selectors '<JSON>'` |
| `registry.py` | `list_tools` / `get_tool` / `call_tool` |
| `__init__.py` | 包导出 |

> `validate` 标了 `internal_only`：不进默认工具面，也不进设置页展示，只由内部修复链路直接调用。

新增 Tool：在本目录加 `<name>.py`，再在 `registry.py` 的 `_TOOLS` 挂一条。
