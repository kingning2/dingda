# packages/client/runtime

运行时基座：HTTP 传输、能力开关、Server 状态、错误上报。

包名 `@v2/runtime`。

## 文件

- `src/api-error.ts`
- `src/app-alert.ts`
- `src/capabilities.ts`
- `src/dismiss-boot-splash.ts`
- `src/error-reporting.ts`
- `src/http-client.ts`
- `src/server-provider.tsx`
- `src/server.ts`
- `src/window.ts`

## 依赖

- 工作区：**无**（叶子包）
- 外部：`@tauri-apps/api`
- peer：`react`

**这是叶子包，不许引任何 `@v2/ui-*`。** `app-preload.ts` 曾住在这里并 import
`@v2/ui-crawler/*`，形成「基座依赖业务包」的方向反转。启动预载已迁到
`apps/web/src/boot/`，`ServerProvider` 只负责 Server 状态。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
