# contracts

与前端 `src/contracts/` 对齐的 Pydantic 模型。改字段先改契约，再改 `api/` 和 React。  
这里没有业务逻辑、不开浏览器。

## 本目录文件

### `account.py`

账号列表/补丁/删除/个人主页。`AccountPlatform`、`AccountRecord`、`AccountProfileView`、会话徽章 `AccountSessionView`、按钮 `AccountActionsView`。对应 `/v1/accounts`。

### `channel.py`

扫码：`QrStartRequest`（platform）、`QrStartResponse`、`QrCheckResponse`（二维码、状态、cookie 成功时）。对应 `/v1/channel/qr/*`。

### `agent.py`

Agent HTTP：探活骨架、默认 CLI 偏好，以及 AI 工作对话快照（`AgentWorkDetailResponse` / `AgentWorkPutRequest`）。完整 Run/SSE 尚未定义。

### `crawler.py`

爬虫任务创建入参骨架（`CrawlerTaskCreate`）。产品搜品（CLI skill 工具）不经过这套 DTO。

### `research.py`

调研启动请求骨架（`ResearchRunRequest`）。

### `watch.py`

商品监控共享词表：`SoldState`（unknown / on_sale / sold / delisted / gone）与 `WatchState`（active / paused / archived），以及 `is_finished`。

crawler 产出售出态、tools 透传、domains.watch 消费，三包都依赖 contracts，所以词表放这里，避免各方各写一套字符串。**值即落库值，改值等于改数据，必须配迁移。** 售出态的关键词映射属平台知识，在 `crawler/sources/<platform>/extract.json`。

### `__init__.py`

包标记。

## 子目录

无。路由：[../api/README.md](../../../api/src/api/README.md)。
