# Copilot 域：AG-UI 事件映射

产品路径（经 Rust 中转）：

```
React
  → Tauri IPC copilot_run_start（Rust 注入 AI 凭据）
  → Python pipe POST /v1/copilot/run_start
    → LangGraph task_copilot 工作流
      → pipe Event copilot.run（snake_case AG-UI 子集）
        → Rust 转发 Tauri app/copilot/agui
          → React listenCopilotAgui

取消：copilot_run_abort → pipe /v1/copilot/run_abort
就绪：copilot_ready（sidecar health_check）
```

遗留：`POST /v1/copilot/agui` HTTP SSE 仅测试/兼容，前端不得直连。

## 事件子集

见 [`agui_event.schema.json`](agui_event.schema.json)。

推理流（DeepSeek / 方舟 ``reasoning_content``）::

```
REASONING_MESSAGE_START → REASONING_MESSAGE_CONTENT* → REASONING_MESSAGE_END
```

正文与工具调用::

```
TEXT_MESSAGE_* / TOOL_CALL_*
```

## 服务端工具

`start_price_compare` / `control_run`；任务上下文由前端 `state` 快照注入。
