# cli

外部 CLI Agent Runtime：在 Python Server 内启动 Codex / Claude / OpenCode，
按 **skill** 暴露 dingda 工具，流式产出事件。

前端经 `/v1/agent/runtimes/...` SSE 调用；**不再**由 Tauri `launch_agent_runtime` spawn。
产品侧的进程内 Agent（LLM + Tool 循环）在 [../../../agent/src/agent/](../../../agent/src/agent/)，两者不要混用。

依赖方向：`api / tools / crawler → cli`。

## 本目录文件

### `base.py` — 唯一基类

`CliRuntime`：一次会话的生命周期 —— 解析可执行文件 → 拼 prompt（工具走 skill 注入）→ spawn
→ 流式解析 → 会话日志。`resolve_binary` / `compress_payload` / `encode_stdin` 都是它的方法，
`cancel_run(run_id)` 也在本文件（进程表）。

**本文件不写「是哪个 CLI」**：差异全在 [agents.py](agents.py) 的插头里。
`run(..., role=...)` 按**角色**取策略（提示词怎么拼 / 注入哪些 Skill / cwd 落哪），
不写「是不是子 agent」—— 差异全在 [roles.py](roles.py)。

### `agents.py` — 三个 CLI 插头 + 注册表

`CodexRuntime` / `ClaudeRuntime` / `OpenCodeRuntime` 与 `get_runtime` / `list_runtime_ids` /
`resolve_binary` 收在同一文件：插头只写「本 CLI 长什么样」（`id` / `name` / `binary` /
`path_env` / `stream_format` 与 `build_args`），其余能力全在基类。

`resolve_binary` 探测顺序：`preferred → DINGDA_*_PATH → 托管目录 → PATH（Windows 并上注册表 PATH）→ 已知安装目录`。

### `roles.py` — 会话角色

父（编排）/ worker（选品）/ child（修复）三种角色：提示词怎么拼、注入哪些 Skill、
工作目录落哪、给 CLI 子进程塞哪些环境。

- `compose_prompt` 只在基类写一遍，角色只声明 `persona` / `skill_ids` / `uses_system_prompt`
- 临时目录统一走 `scratch_workdir(prefix)`：按角色前缀进程内复用，一律不落仓库
  （cwd 在仓库 = 子 agent 能顺手读到现成答案）
- `get_role(name)` / `list_role_ids()` 也在本文件

### `prompts.py` — 人设正文与拼装

`PERSONAS`（orchestrator / worker 的提示词正文，dict 按 persona 键取）+ `compose_role_prompt`
把人设、Skills、叮答托管的先前对话与用户原文拼成 stdin prompt；有 `session_id` 续聊时
只传 Skill 提醒 + 用户增量。

### `skill.py` — Skill 渲染与安装

`SKILLS` 是 map（名字 → `SkillSpec`）；`WORKER_SKILL_NAMES` / `ORCHESTRATE_SKILL_NAMES`
是数组，角色按用途取，不各抄一份清单。

从 [skills/](skills/) 的静态模板渲染，注入 prompt 并复制到工作目录 `.dingda-skills/`；
`python -m cli.skill --install` 装到各 runtime 的 skills 目录作 fallback。
**工具注入只有这一条路径**，没有别的注入分支。

### `steps.py`

把 toolCall / toolResult / live frame 收成前端 step / page；**kind 由后端决定**。
步骤文案不得出现命令 / 路径 / 文件内容（收口在 `_TOOL_LABELS` / `_OPAQUE_TOOLS`）。

### `stream.py`

`parse_lines(format_id, line, state=...)`：Codex JSON / Claude stream-json / OpenCode JSON /
plain → AgentEvent dict。OpenCode 的 `part.text` 是整段快照不是增量，靠 `state` 里的游标切片。

### `live.py`

直播帧总线：按 run_id 登记队列；`preview` 工具经
[tools/live_push.py](../../../../tools/src/tools/live_push.py) 投帧，spawn 侧 `drain` 进 SSE。
队列有界，满了丢最旧帧，避免阻塞浏览器推帧。

### `repair.py`

`propose_dom_patch(snap, validate_url=None)`：把 `DomSnapshot` 发给外部 CLI（`role="child"`），
从 stdout 抠出 JSON 选择器补丁写回 `DomPatch`。给了 `validate_url` 就把修复现场塞进子 agent
环境（`run_env`），它跑 `python -m tools.validate_cli` 自验。
编排（指纹 → AI 轮 → 验证 → 写回）在 `crawler/extraction/repair/`。

### `spawn.py`

`run_cli` / `cancel_run`：给调用方的稳定入口，按 id 取插头再起会话。生命周期不在本文件。

### `lifecycle.py` — 阶段状态机

`AgentPhase`（StrEnum）/ `AgentRunSnapshot` / `can_transition`：一次 AgentRun 的合法迁移边，
供 Store、子会话与 SSE `agentPhase` 共用。父 / worker / child 各一条快照用 `parent_run_id` 串树。

### `runs.py` — 运行快照存储

`AgentRunStore` 插座 + `MemoryAgentRunStore`（进程内 dict，与 live hub 同寿命）：按 `run_id`
登记 / 查询 / 阶段迁移，列出某父 run 下的子 run。非法迁移打 warning 并拒绝。

### `subagent.py` — 子会话插座 + CLI 插头

`SubAgentSession` 插座（持有 `SubAgentResult`）+ `CliSubAgentSession`：起 / 续 / 停子 CLI、
写 `AgentRunStore`、向父 run 推 `agentPhase`。`_execute` 拆成 `_open_run`（开快照）→
`_consume_events`（消费 run_cli 事件）→ `_finish`（定相）三步。`crawler.needs_repair` 由这里识别。

### `registry.py` — 编排单例

`get_run_store` / `get_subagent_session` / `reset_orchestrate_singletons`：进程内单例入口。

### `__init__.py`

包标记。

## 子目录

- [skills/](skills/) — 5 个 Skill 静态模板（`dingda-crawl` 等）
