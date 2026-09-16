---
name: dingda-orchestrate
description: 父编排器专用：派工子会话、查进度、取消、调度 DOM 修复后再续聊。
---

# 叮答编排工具

在 shell 执行（stdout 纯 JSON）：

```bash
{{ENTRY}} child_run --task "任务说明"
{{ENTRY}} child_resume --session-id "<id>" --message "继续…"
{{ENTRY}} child_cancel --run-id "<id>"
{{ENTRY}} child_status --run-id "<id>"
{{ENTRY}} repair_dom --platform xianyu --item-id "<id>"
```

## 字段

- `child_run`：可选 `--role worker`（默认）、`--runtime-id`、`--model-id`
- 返回：`ok` / `run_id` / `session_id` / `phase` / `error_code` / `repair` / `summary`
- `phase=needs_repair` 或 `error_code=crawler.needs_repair` → 先 `repair_dom` 再 `child_resume`
- `child_status`：也可 `--session-id`；看当前 `phase` / `step`

## 硬规则

1. 不要自己跑 `search` / `product` / `compare` / `login`
2. 不要翻仓库源码目录
3. DOM 失效必须经本 Skill 的 `repair_dom`，不要让 worker 自修
