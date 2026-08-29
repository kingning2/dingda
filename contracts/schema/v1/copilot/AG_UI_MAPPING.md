# Copilot 域：AG-UI 事件映射

CopilotKit 前端（`@ag-ui/client` HttpAgent）**直连** sidecar 副驾 HTTP 端点（直连例外由
CHG-20260829-007 确认：Rust 不转发业务流量，仅做端口发现）：

```
CopilotKit (HttpAgent, POST RunAgentInput)
  → Python sidecar 辅助 HTTP 服务（127.0.0.1 随机端口，产品模式随 --ipc 一并拉起）
    → POST /v1/copilot/agui（text/event-stream）
      → LangGraph task_copilot 工作流
        → SSE 帧回写：`data: {AG-UI 事件 json}\n\n`

端口发现：Rust 经 pipe RPC /v1/copilot/http_info 取端口 → 命令 copilot_endpoint 返回
端点 URL 给前端。客户端断开（fetch abort）即取消本轮运行。
```

## 事件子集与触发时机

| AG-UI 事件 | 触发时机 | 必带字段 |
|---|---|---|
| `RUN_STARTED` | 工作流开始执行 | threadId?→thread_id, run_id |
| `TEXT_MESSAGE_START` | 助手消息开始 | message_id, role="assistant" |
| `TEXT_MESSAGE_CONTENT` | LLM token/增量输出 | message_id, delta |
| `TEXT_MESSAGE_END` | 助手消息结束 | message_id |
| `TOOL_CALL_START` | agent 发起工具调用 | tool_call_id, tool_name |
| `TOOL_CALL_ARGS` | 工具参数增量 | tool_call_id, args_delta |
| `TOOL_CALL_END` | 工具参数结束 | tool_call_id |
| `TOOL_CALL_RESULT` | 工具执行结果 | tool_call_id, content |
| `RUN_FINISHED` | 本轮结束 | — |
| `RUN_ERROR` | 失败终止 | message, code |

## 约束

- SSE 帧：`data: {event json}\n\n`，UTF-8，`Content-Type: text/event-stream`，连接关闭即流结束。
- 事件载荷以 `agui_event.schema.json` 为准（字段 `type`/`thread_id`/`run_id` 等snake_case
  自定义信封，事件枚举与 AG-UI 对齐）；任务卡片富展示由前端按 `tool_call_id` 关联工具结果渲染。
- 服务端工具清单（第一期）：`start_price_compare` / `control_run`；任务列表与详情由前端经
  `state` 快照注入。
- 凭据经 `forwardedProps.default_base_url / default_api_key / default_model` 传递（前端取自
  ai_config_get 的首个账号），仅存在于本机回环连接。
