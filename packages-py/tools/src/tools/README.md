# tools

产品 Agent 与 CLI skill **共用**的选品能力。每个 Tool 一个文件（契约 + `run_*`），`registry.py` 负责注册。

不要在 CLI skill / Agent 里复制命令。不要在 Tool 里 `import playwright` / `camoufox`。

## 已注册的 Tool（`registry.py::_TOOLS`）

| Tool | 默认超时 | 说明 |
|------|---------|------|
| `search` | 300s | 关键词 / 图 / 链接搜品（xianyu / xiaohongshu / ali1688） |
| `product` | 45s | 单品详情（xianyu / xiaohongshu） |
| `browse` | 600s | 连贯浏览：一个 page 内 列表 → 逐个点开详情 → 返回 |
| `compare` | 90s | 1688 多轮同款比价 |
| `preview` | 45s | 打开任意 URL，直播截图给前端 |
| `login` | 300s | 平台扫码登录（阻塞等用户扫码） |
| `child_run` | 3600s | 父编排：拉起 worker 子会话 |
| `child_resume` | 3600s | 父编排：按 session 续聊 worker |
| `child_cancel` | 30s | 父编排：终止子会话 |
| `child_status` | 10s | 父编排：查子会话 phase / step |
| `repair_dom` | 900s | 父编排：调度 DOM 修复后再 resume |
| `validate_selectors` | 90s | **内部工具**（`internal_only=True`）：在修复现场页面试跑候选选择器 |

## 支撑模块（不注册为 Tool）

| 文件 | 职责 |
|------|------|
| `session.py` | 抓取会话编排：一次 `acquire` 覆盖多步（一台浏览器多步共用） |
| `account_cookie.py` | 爬虫 / 预览用账号 Cookie 与会话解析 |
| `recovery.py` | 抓取会话恢复（登录失效 → 扫码 → 重试） |
| `headed.py` | 有头模式开关：读 `DINGDA_CRAWL_HEADED`（排障用） |
| `live_push.py` | 在 `tools.cli` 子进程里把截图 POST 回 Server live-frame |
| `cli.py` | 通用命令行入口：按 registry 的 Input Schema 调工具并输出 JSON |
| `validate_cli.py` | `validate_selectors` 的命令行形态：`python -m tools.validate_cli --selectors '<JSON>'` |
| `registry.py` | `list_tools` / `get_tool` / `call_tool` |
| `__init__.py` | 包导出 |

## `internal_only` 的收口

`validate_selectors` 标了 `internal_only=True`，本意是「不进默认工具面」。**当前只有
`cli.py` 过滤它**（`if spec.internal_only: continue`）；`agent/core/agent.py::_openai_tools()`
直接遍历 `list_tools()`，会把它一并交给产品 Agent。修复链路本身走的是
`validate_cli.py`（`cli/repair.py` 写死的命令行），不依赖这个 ToolSpec。

新增 Tool：在本目录加 `<name>.py`，再在 `registry.py` 的 `_TOOLS` 挂一条，并补
`cli/steps.py` 的 `_TOOL_LABELS` 与 `_BROWSER_CRAWL_BASE`（会推直播帧的才进后者）。
