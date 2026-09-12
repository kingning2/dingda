# apps/web

Web 应用装配：入口、路由表、页面（Vite 根）。

包名 `@v2/app-web`。

## 脚本

本包是 **Vite 根**，构建脚本归本包所有；仓库根的 `pnpm dev` / `pnpm build` / `pnpm preview`
只是转发过来（Tauri 的 `beforeDevCommand: pnpm dev` 走的也是这条链）。

```bash
pnpm dev       # vite        （devUrl http://localhost:1420）
pnpm build     # vite build  （产物 apps/web/dist）
pnpm preview   # vite preview
```

类型检查不在本包：根 `pnpm build` 是 `tsc && pnpm --filter @v2/app-web build`，
`tsc` 在仓库根跑全量（`apps` + `packages`），所以 `typescript` 声明在根。

构建工具（`vite` / `@vitejs/plugin-react` / `@tailwindcss/vite`）声明在**本包**的
`devDependencies` —— 谁用谁声明。`tailwindcss` 本身不用声明：`@tailwindcss/vite`
已把它作为直接依赖带上。

## 文件

- `src/App.css`
- `src/App.tsx`
- `src/boot/boot-gate.tsx`
- `src/boot/preload.ts`
- `src/main.tsx`
- `src/pages\accounts-page.tsx`
- `src/pages\agents-page.tsx`
- `src/pages\ai-work-page.tsx`
- `src/pages\assets-page.tsx`
- `src/pages\community-page.tsx`
- `src/pages\crawler-page.tsx`
- `src/pages\design-systems-page.tsx`
- `src/pages\error-test-page.tsx`
- `src/pages\http-status-page.tsx`
- `src/pages\integrations-page.tsx`
- `src/pages\plugins-page.tsx`
- `src/pages\projects-page.tsx`
- `src/pages\status-pages.tsx`
- `src/routes\animated-outlet.tsx`
- `src/routes\layouts\app-layout.tsx`
- `src/routes\layouts\entry-layout.tsx`
- `src/routes\layouts\workspace-layout.tsx`
- `src/routes\pages\home-route.tsx`
- `src/routes\pages\projects-route.tsx`
- `src/routes\pages\status-routes.tsx`
- `src/routes\pages\work-route.tsx`
- `src/routes\route-handle.ts`
- `src/routes\route-transition.ts`
- `src/routes\router.tsx`
- `src/vite-env.d.ts`

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/routes / @v2/runtime / @v2/ui-account / @v2/ui-agent / @v2/ui-ai / @v2/ui-crawler / @v2/ui-feedback / @v2/ui-home / @v2/ui-layout / @v2/ui-primitives / @v2/ui-theme
- 外部：lucide-react / motion / react-router-dom
- peer：react / react-dom

## 启动编排（`src/boot/`）

- `preload.ts` —— `preloadAppHome()`：Server 就绪后拉 Agent 目录 + 账号 + 最近会话；
  `ensureDiscoveryScanned()`：进首页前的兜底。
- `boot-gate.tsx` —— `<BootGate>`：预载完成前不挂路由（HTML 启动屏继续挡着）。

**为什么在这里而不是 `@v2/runtime`**：这段编排要组合 Agent 域与账号域，两个域互不引用；
放在基座包里等于让 `runtime` 反向依赖业务包。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
