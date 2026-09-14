# packages/client/ui-ai

AI 消息渲染：消息块、Markdown、思考过程。

包名 `@v2/ui-ai`。

## 文件

目录职责与分层见 [`src/README.md`](src/README.md)；聊天记录部分见
[`src/chat/README.md`](src/chat/README.md)。

**这里不再维护文件清单** —— 原来那份是手工生成的全量列表，改一次目录就要改两处，
而且已经过期（列着 `src/scheduler.tsx`，该文件已拆入 `src/chat/` 与 `src/send.ts`）。

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/runtime / @v2/ui-agent / @v2/ui-composer / @v2/ui-crawler / @v2/ui-primitives
- 外部：@tanstack/react-virtual / lucide-react / react-markdown / remark-gfm
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
