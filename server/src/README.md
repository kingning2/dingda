# server/src

Python Server 的产品代码根目录。桌面壳用 uvicorn 拉起本包：对外是 REST（给 React），另有 `dingda-mcp` stdio（给 Codex/Claude）。

依赖方向（跨层 import 算错）：

```text
api / mcp → domains / tools → crawler / channels → browser
```

## 本目录文件

### `app.py`

FastAPI 应用工厂 `create_app(settings)`。做四件事：

1. 用 `Settings` 建 `FastAPI(title="DingDa v2")`，lifespan 走 `core.lifespan`
2. CORS：本机 Vite `1420`、Tauri origin
3. `include_router(api_router)`，即 [api/README.md](api/README.md)
4. `register_exception_handlers`：把 `AppError` 变成 JSON

改端口/中间件/全局异常处理看这里。业务路由不要往这里堆。

### `__main__.py`

控制台脚本 `dingda-v2`。解析 `--host/--port/--log-level/--reload`，`Settings.from_env`，`configure_logging`，然后 `uvicorn.run(create_app(settings))`。

MCP 入口不在这里，在 [mcp/README.md](mcp/README.md) 的 `server.py`（`dingda-mcp`）。

### `__init__.py`

包标记，无逻辑。

## 子目录

每个子目录自己的 README 列**该层每一个文件**。这里只指路：

| 目录 | 打开它当… |
|------|-----------|
| [api/](api/README.md) | 给前端的 HTTP 路径（`/health`、`/v1/accounts`…） |
| [contracts/](contracts/README.md) | 和前端共享的请求/响应模型 |
| [domains/](domains/README.md) | HTTP 后面的账号/扫码/runtime 编排 |
| [channels/](channels/README.md) | 闲鱼/小红书登录、mtop、IM、发品（平台账号语义） |
| [crawler/](crawler/README.md) | 搜品/详情采集（走 Browser，不负责扫码） |
| [browser/](browser/README.md) | 启动浏览器、Page、Cookie、滑块原语（无商品逻辑） |
| [tools/](tools/README.md) | MCP/Agent 可调用的工具名与实现 |
| [mcp/](mcp/README.md) | 把 tools 挂到 FastMCP stdio |
| [agent/](agent/README.md) | 产品侧 Agent/调研 workflow（骨架） |
| [core/](core/README.md) | 配置、日志、启动、预热 |
| [infrastructure/](infrastructure/README.md) | SQLite、内存事件总线 |
| [shared/](shared/README.md) | `AppError` 错误码 |
