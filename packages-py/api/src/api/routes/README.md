# routes/

全部 HTTP 端点，**一端点一文件**。文件名 = 动作（`qr_start.py`、`add_targets.py`），
每个文件导出一个无前缀的 `router`，由域 `__init__.py` 统一挂前缀与 tags。

## 设计说明

- `__init__.py`（本文件）只做聚合：按固定顺序 `include_router` 挂成 `api_router`，
  `app.py` 只 import 这一个入口；新增域必须在这里挂上
- 单端点域放平铺文件：`health.py`、`bootstrap.py`、`research.py`
- 多端点域建目录，共享 DTO / 映射放各域 `_dto.py`，响应模型一律放 `contracts`
- 例外：account 的列表端点路径为空前缀，前缀落在各动作文件里（`APIRouter(prefix="/v1/accounts")`），
  域 `__init__.py` 只留 tags——FastAPI 不允许「子路由空路径 + include 空前缀」两级拼接
- 域内 include 顺序保持与 URL 语义一致，更具体的路径不互相遮蔽

## 子目录

- [agent/](agent/README.md) — `/v1/agent`
- [account/](account/README.md) — `/v1/accounts`
- [channel/](channel/README.md) — `/v1/channel`
- [crawler/](crawler/README.md) — `/v1/crawler`
- [runtime/](runtime/README.md) — `/v1/runtime`
- [watch/](watch/README.md) — `/v1/watch`

## 平铺文件

- `health.py` — `GET /health`，Rust 壳探活，不触发完整预热
- `bootstrap.py` — `GET /v1/bootstrap`，壳首屏快照 + `BackgroundTasks` 完整预热
- `research.py` — `/v1/research` 前缀，**目前是空骨架**
- `sse.py` — SSE 帧格式化，agent / crawler 流式端点共用
