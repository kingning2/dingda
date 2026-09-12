# apps/web

Web 应用装配：入口、路由表、页面（Vite 根）。

包名 `@v2/app-web`。

## 文件

- `src/App.css`
- `src/App.tsx`
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

- 工作区：@v2/contracts / @v2/routes / @v2/runtime / @v2/ui-account / @v2/ui-agent / @v2/ui-ai / @v2/ui-crawler / @v2/ui-feedback / @v2/ui-home / @v2/ui-layout / @v2/ui-primitives
- 外部：lucide-react / motion / react-router-dom
- peer：react / react-dom

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
