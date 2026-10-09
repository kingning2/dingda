# tools

产品 Agent 与 CLI skill **共用**的选品能力。**每个工具一个目录**：`tools/<name>/__init__.py`
放契约 + `run_*` + `spec`，`registry.py` 自动发现，不需要手工注册。

不要在 CLI skill / Agent 里复制命令。不要在 Tool 里 `import playwright` / `camoufox`。

## 目录结构

### 工具目录（registry 自动发现）

| 目录 | 工具 | 职责 |
|------|------|------|
| [search/](search/__init__.py) | `search` | 关键词 / 图 / 链接搜品（含 ali1688） |
| [product/](product/__init__.py) | `product` | 单品详情（xianyu / xiaohongshu） |
| [compare/](compare/__init__.py) | `compare` | 1688 多轮同款比价 |
| [preview/](preview/__init__.py) | `preview` | 打开任意 URL，直播截图给前端预览 |
| [login/](login/__init__.py) | `login` | 平台扫码登录（阻塞等用户扫码） |
| [validate/](validate/__init__.py) | `validate_selectors` | **内部工具**：修复现场试跑候选选择器（`internal_only`） |

每个目录的 `__init__.py` 导出 `TOOL_NAME`、`TOOL_DESCRIPTION`、`XInput`/`XOutput`、
`run_*`、`DEFAULT_TIMEOUT_S` 与 `spec = ToolSpec(...)`。

### 支撑模块（平铺，不是工具）

| 文件 | 职责 |
|------|------|
| `spec.py` | `ToolSpec` 注册信息定义 |
| `registry.py` | `pkgutil` 自动发现工具目录；`list_tools` / `get_tool` / `call_tool` |
| `scaffold.py` | 脚手架：`python -m tools.scaffold <name>` 生成新工具骨架 |
| `cli.py` | 通用命令行入口：按 registry 的 Input Schema 调工具并输出 JSON |
| `account_cookie.py` | 爬虫 / 预览用账号 Cookie 与会话解析 |
| `recovery.py` | 抓取会话恢复（登录失效 → 扫码 → 重试） |
| `live_push.py` | 在 `tools.cli` 子进程里把截图 POST 回 Server live-frame |
| `validate_cli.py` | validate 的命令行形态：`python -m tools.validate_cli --selectors '<JSON>'` |
| `__init__.py` | 包导出 |

> `validate` 标了 `internal_only`：不进默认工具面、不进 `tools.cli`，也不进设置页展示，
> 只由内部修复链路直接调用。

## 新增 Tool

```bash
uv run python -m tools.scaffold <name>   # 生成 tools/<name>/__init__.py 骨架
```

把骨架里的 `run_<name>` 换成真实逻辑即可；registry 下次导入自动发现，`tools.cli`
子命令也随之出现。详见 [tool-architecture SKILL](../../../.agents/skills/tool-architecture/SKILL.md)。
