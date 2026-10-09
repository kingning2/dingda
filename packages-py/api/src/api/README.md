# api

给 React / Tauri WebView 的 HTTP。这里**只做路由**：校验入参、调 `domains`，不写闲鱼签名、不开浏览器。

## 目录结构

- [routes/](routes/README.md) — 全部 HTTP 端点，**一端点一文件**，按域分目录；`routes/__init__.py` 是唯一聚合点（`api_router`），`app.py` 只 import 它
- [boot/](boot/README.md) — FastAPI lifespan 与渐进式预热
- [lib/](lib/README.md) — 被多个端点 / 启动钩子复用的模块（如监控取数插头）
- `exceptions.py` — 全局异常处理注册（`AppError` → HTTP）
- `app.py` — `create_app()` 工厂：CORS、`api_router`、异常处理、lifespan
- `__main__.py` — `uv run python -m api` 入口

## 端点总览

| 域 | 前缀 | 内容 |
|----|------|------|
| [routes/health.py](routes/health.py) | `/health` | Rust 壳探活 |
| [routes/bootstrap.py](routes/bootstrap.py) | `/v1/bootstrap` | 壳首屏快照 + 后台预热 |
| [routes/runtime/](routes/runtime/README.md) | `/v1/runtime` | Python 进程就绪状态 |
| [routes/channel/](routes/channel/README.md) | `/v1/channel` | 扫码登录 |
| [routes/account/](routes/account/README.md) | `/v1/accounts` | 账号库读写 |
| [routes/agent/](routes/agent/README.md) | `/v1/agent` | 偏好、CLI 目录、AI 工作对话、Agent 运行 |
| [routes/crawler/](routes/crawler/README.md) | `/v1/crawler` | 搜品 / 单品详情（含 SSE 直播） |
| [routes/research.py](routes/research.py) | `/v1/research` | 空骨架 |
| [routes/watch/](routes/watch/README.md) | `/v1/watch` | 商品监控 |

## 新增端点

1. 在 `routes/<域>/` 建 `<动作>.py`（单端点域直接放 `routes/` 平铺文件）
2. 域 `__init__.py` 里 `include_router`（顺序保持与 URL 语义一致）
3. 多个端点共用的请求模型放域 `_dto.py`；响应模型一律放 `contracts`

DTO 在 [../../../contracts/README.md](../../../contracts/src/contracts/README.md)。
