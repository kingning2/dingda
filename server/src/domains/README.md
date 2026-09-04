# domains

给 HTTP 用的**应用编排**：账号表、扫码任务、知识库、进程快照。  
不是闲鱼签名实现（那是 channels），不是搜品（crawler），不是 Page（browser）。

## 本目录文件

### `__init__.py`

说明本包边界，无业务逻辑。

## 子目录

- [account/](account/README.md) — SQLite 账号、资料补全、闲鱼 token 定时
- [channel/](channel/README.md) — 扫码 session 表 + 调 `channels.registry`；另有未接线的 WSS 服务骨架
- [knowledge/](knowledge/README.md) — RAG/知识库骨架
- [runtime/](runtime/README.md) — Python 进程 uptime 快照
