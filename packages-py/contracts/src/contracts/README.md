# contracts

与前端 `src/contracts/` 对齐的 Pydantic 模型。改字段先改契约，再改 `api/` 和 React。  
这里没有业务逻辑、不开浏览器。

## 本目录文件

### `account.py`

账号列表/补丁/删除/个人主页。`AccountPlatform`、`AccountRecord`、`AccountProfileView`、会话徽章 `AccountSessionView`、按钮 `AccountActionsView`。对应 `/v1/accounts`。

### `channel.py`

扫码：`QrStartRequest`（platform）、`QrStartResponse`、`QrCheckResponse`（二维码、状态、cookie 成功时）。对应 `/v1/channel/qr/*`。

### `agent.py`

Agent HTTP：探活骨架、默认 CLI 偏好、AI 工作对话快照（`AgentWorkDetailResponse` /
`AgentWorkPutRequest` / `AgentWorkListResponse`），以及活跃 run 探针
（`AgentActiveRunView`：`run_id=None` 表示这个 work 下没有在跑的运行，客户端据此走
「上次执行已中断」）。

运行请求体 `AgentRunRequest` 与 SSE 事件**不在这层** —— 前者定义在 `api/agent_run.py`
（放这里会让 `agent_run` 反过来 import 路由模块，绕成环），后者是线协议里的
`AgentEvent`（TS 侧 `packages/contracts/src/agent-event.ts`）。

### `crawler.py`

爬虫任务创建入参骨架（`CrawlerTaskCreate`）。产品搜品（CLI skill 工具）不经过这套 DTO。

### `research.py`

调研启动请求骨架（`ResearchRunRequest`）。

### `watch.py`

商品监控共享词表：`SoldState`（unknown / on_sale / sold / delisted / gone）与 `WatchState`（active / paused / archived），以及 `is_finished`。

crawler 产出售出态、tools 透传、domains.watch 消费，三包都依赖 contracts，所以词表放这里，避免各方各写一套字符串。**值即落库值，改值等于改数据，必须配迁移。** 售出态的关键词映射属平台知识，在 `crawler/sources/<platform>/extract.json`。

### `llm.py`

模型凭据与供应商目录：`LlmProviderView`（目录一行）、`LlmCredentialRecord`（含掩码 key）、增改请求、`LlmModelListRequest` / `LlmModelListResponse`（可用模型列表）、`LlmCheckView`（连通性检测结果）、`LlmImportEnvResponse`。

三条约定值得记住：

- **`api_key` 只进不出**：请求体里是原文，响应体里只有 `api_key_masked`。改凭据时 `api_key` 为空表示「不改」
- **`base_url` 的「不改」与「清空」用 `model_fields_set` 区分**：字段没出现 = 不改，出现且为 `None` = 恢复供应商默认地址。不用额外的 `clear_*` 开关
- **拉模型列表拉不到不是错误**：与检测端点同口径，回 200 + `ok=False` + `message`。
  `LlmModelListRequest` 里**没有 `model` 字段**（拉列表本就是为了知道该填什么），
  `LlmModelListResponse.current_model` 只在「用已保存凭据拉」时才有值

供应商 id **不写 Literal**：目录是数据驱动的（`agent.llm.providers`），写死枚举等于把「新增供应商」变成跨包改动。

### `__init__.py`

包标记。

## 子目录

无。路由：[../api/README.md](../../../api/src/api/README.md)。
