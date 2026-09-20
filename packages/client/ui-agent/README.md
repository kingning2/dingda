# packages/client/ui-agent

Agent 域：运行事件归约、SSE 流、工作对话持久化。

包名 `@v2/ui-agent`。

## 目录

```text
src/
  api.ts              工作对话的 Server HTTP（读写 /v1/agent/works/{id}）+ 在跑 run 探针
  work-list.ts        「最近工作」预热，写 app-state 的 recentWorks 切片
  status-tone.ts      状态徽标六档语义色常量
  run/
    stream.ts         SSE 收发（裸 fetch，统一 http-client 做不了流式）；起手与接回
    phase.ts          运行阶段到 UI 的唯一映射 AGENT_RUN_PHASE_MAP
    reducer.ts        SSE 事件折叠成助手消息状态
  ui/
    icon.tsx          Agent 图标
```

## 文件说明

- `src/api.ts` — 工作对话的 Server HTTP：`fetchAgentWorkDetail` / `fetchAgentWorkList` /
  `putAgentWorkDetail` / `fetchActiveAgentRun`。**全部走 `@v2/runtime/http-client`**，
  不自己拼 baseUrl。`fetchActiveAgentRun(workId)` 是进页面时的活跃探针（
  `GET /v1/agent/works/{id}/active-run`）：返回在跑 run 的 id，没有则 `null`；探针读不到
  （旧服务端 / 网络抖动）一律按「没有在跑」处理，退回「上次执行已中断」那条路。
  被 `ui-ai/src/work/session.ts`、`ui-ai/src/chat/use-work-detail.ts` 使用。

- `src/work-list.ts` — `refreshRecentWorks()`：拉最近工作写进 `@v2/app-state` 的
  `recentWorks` 切片。与账号发现（`@v2/ui-account/account-discovery`）刻意分开 ——
  两者写同一份 store，但各自只管自己那半边，互不引用；「一起做」的启动编排属于应用层，
  放在 `apps/web/src/boot` 组合。
  被 `apps/web/src/boot/preload.ts` 使用。

- `src/run/stream.ts` — 一次 Agent 运行的两条入口，共用同一个 `readSse` 循环：
  - `startAgentRunWithEvents(req)` — `POST /v1/agent/runtimes/{id}/run` 起手；`req`
    带 `runId` / `workId`（work_id 只能走 body，这条路径里没有 work 信息）
  - `resumeAgentRun(runId, after)` — `GET /v1/agent/runtimes/runs/{id}/events?after=`
    **接回**服务端还在跑的那一轮：`after=0` 是从头整条重建，`after=lastSeq` 是断点续传
  - 两者都读 `id:` 行（服务端 `seq`）并交给 `onSeq` 回调 —— 客户端据此记住断点，
    掉线时从这里续传而不是重跑
  - `AgentStreamError.status` 区分 404（run 已结束并被回收 → 别重试）与瞬时断流；
    `AgentRunHandle` 给 `detach`（不看这一轮，run 继续在服务端跑）与 `cancel`（叫停）

  这里**必须裸 `fetch`**：统一 http-client 会一次性读完整个响应，做不了流式（见文件内注释）。
  被 `ui-ai/src/work/send.ts` 使用。

- `src/run/phase.ts` — 运行阶段到 UI 的**唯一映射** `AGENT_RUN_PHASE_MAP`：阶段、徽标样式、
  流式块类型、思考期是否隐藏正文。新增阶段只改这里。
  被 `reducer.ts`、`ui-ai/src/chat/`（schedule / working-status / chat / chat-turn）、
  `ui-ai/src/work/send.ts` 使用。

- `src/run/reducer.ts` — 把 SSE 事件折叠成助手消息状态：时间线按到达顺序交错（思考 ↔ 工具 ↔
  正文）、步骤 upsert / patch、阶段推进、乐观发送、按用户消息截断。
  被 `ui-ai/src/work/send.ts`、`ui-ai/src/chat/use-work-detail.ts` 使用。

- `src/ui/icon.tsx` — Agent 图标 `AgentIcon`：按 id 选 `.svg` / `.png`；`MONO_ICONS` 里的单色图标
  走 CSS mask 跟随文字色；表里没有的 id 回落成首字母方块。
  被 `ui-ai/src/panel/settings.tsx`、`ui-composer/src/composer-agent-picker.tsx` 使用。

- `src/status-tone.ts` — 状态徽标六档语义色常量 `STATUS_TONE`：neutral / active / ready /
  live / pending / failed。被 `run/phase.ts`、`run/reducer.ts` 共用。

## 消费方式（一律走子路径）

`package.json` 的 `exports` 只有 `{ "./*": "./src/*" }` —— **没有包入口**，
消费方一律按 `@v2/ui-agent/<dir>/<file>` 取：

```ts
import { startAgentRunWithEvents } from "@v2/ui-agent/run/stream";
import { AgentIcon } from "@v2/ui-agent/ui/icon";
```

包内互相引用走相对路径，不要绕回包名。

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/runtime
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
