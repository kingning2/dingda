# agent/

`/v1/agent`：AI 工作对话快照与产品 Agent 运行。

- `list_works.py` / `get_work.py` / `put_work.py` — AI 工作对话快照的列表与读写
- `run_work.py` — `POST /works/{work_id}/run` 产品 Agent SSE（进程内 Tool；Agent 为内置
  dingda，模型由 Server 侧 `DINGDA_LLM_*` 决定）

设计说明：
- `_dto.py` 只放请求模型；响应模型在 [contracts/agent](../../../../../contracts/src/contracts/README.md)
- Agent 实现在 [agent 包](../../../../../agent/src/agent/README.md)；早期「外部 CLI Runtime
  探测 / 登录 / 下载 / 直播帧」端点已随外部 CLI 支持整体移除
