# packages/client/runtime

运行时基座：HTTP 传输、能力开关、启动预载、错误上报、Server 状态。

包名 `@v2/runtime`。

## 文件

- `src/api-error.ts`
- `src/app-alert.ts`
- `src/app-preload.ts`
- `src/capabilities.ts`
- `src/dismiss-boot-splash.ts`
- `src/error-reporting.ts`
- `src/http-client.ts`
- `src/server-provider.tsx`
- `src/server.ts`
- `src/window.ts`

## 依赖

- 工作区：@v2/ui-crawler
- 外部：@tauri-apps/api
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
