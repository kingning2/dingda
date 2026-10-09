# agent/

`/v1/agent`：偏好、Agent CLI 目录、AI 工作对话快照、Agent 运行。

- `get_preferences.py` — `GET /preferences` 读默认 Agent + 各 Agent 默认模型映射
- `get_default.py` / `put_default.py` — `GET|PUT /default` 默认外部 Agent id
- `put_default_model.py` — `PUT /default-model` 写某 Agent 默认模型
- `get_runtimes.py` / `put_runtimes.py` — `GET|PUT /runtimes` Agent CLI 扫描目录（含模型）
- `list_works.py` / `get_work.py` / `put_work.py` — AI 工作对话快照的列表与读写
- `run_work.py` — `POST /works/{work_id}/run` 产品 Agent SSE（进程内 Tool + Headroom）
- `run_runtime.py` — `POST /runtimes/{runtime_id}/run` 外部 CLI SSE（Python spawn；codex / claude / opencode）
- `post_live_frame.py` — `POST /runtimes/runs/{run_id}/live-frame` `preview` 工具投递浏览器直播帧
- `cancel_run.py` — `POST /runtimes/runs/{run_id}/cancel` 取消 CLI 运行

设计说明：
- `_dto.py` 只放请求模型；响应模型在 [contracts/agent](../../../../../contracts/src/contracts/README.md)
- CLI PATH 探测 / 下载在 Tauri；启动与流式事件在本域。实现见 [agent 包](../../../../../agent/src/agent/README.md)
