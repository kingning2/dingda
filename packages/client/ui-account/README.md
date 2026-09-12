# packages/client/ui-account

账号域：账号列表、扫码登录、登录态告警。

包名 `@v2/ui-account`。

## 文件

- `src/account-auth-alert.ts`
- `src/account-discovery.ts`
- `src/account-qr-dialog.tsx`
- `src/account-qr.ts`
- `src/account-store.ts`
- `src/accounts-hub.tsx`
- `src/accounts-panel.tsx`
- `src/index.ts`
- `src/mock-data.ts`
- `src/types.ts`

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/routes / @v2/runtime / @v2/ui-primitives
- 外部：lucide-react
- peer：react

## 发现逻辑归本域

`src/account-discovery.ts` 是账号发现的实现（启动拉全部平台 / 登录后刷单平台），
写 `@v2/app-state` 的 accounts 切片。与 `@v2/ui-agent/agent-runtime-scan` 各管各的，
需要「两边一起做」的启动编排在 `apps/web/src/boot`。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
