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

## 静态资源

`public/` 在**本包内**，这是 Vite 的默认 `publicDir`（`<root>/public`）。
里面按 `/xxx` 绝对路径引用，不要写相对路径。

```text
public/logo-mark.svg      →  代码里写 "/logo-mark.svg"
public/agent-icons/*      →  代码里写 `/agent-icons/${id}.svg`
```

**不要把 `public/` 挪回仓库根** —— `publicDir` 相对 Vite 根，挪回去不会报错，
只会让所有图片静默 404、构建产物里一张图都没有。

## 文件

```text
index.html               Vite 入口（含启动屏 HTML）
vite.config.ts           Vite 配置（root: __dirname）
tsconfig.json
public/                  静态资源（Vite publicDir，按 /xxx 引用）
src/
  main.tsx               挂载点
  App.tsx                ServerProvider → BootGate → TooltipProvider → Router
  App.css
  vite-env.d.ts
  boot/
    preload.ts           首页数据预载编排
    boot-gate.tsx        启动闸门
    alert-navigator.ts   把 router.navigate 注入全局告警
  pages/                 页面组件（13 个）
  routes/
    router.tsx           createHashRouter 路由表
    route-handle.ts      路由 handle 类型与标题解析
    route-transition.ts
    animated-outlet.tsx
    layouts/             app-layout / entry-layout / workspace-layout
    pages/               home-route / projects-route / status-routes / work-route
```

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/routes / @v2/runtime / @v2/ui-account / @v2/ui-agent / @v2/ui-ai / @v2/ui-crawler / @v2/ui-feedback / @v2/ui-home / @v2/ui-layout / @v2/ui-primitives / @v2/ui-theme
- dependencies：lucide-react / motion / react / react-dom / react-router-dom
- devDependencies：@tailwindcss/vite / @vitejs/plugin-react / vite

本包是**应用**不是库，所以 `react` / `react-dom` 是 `dependencies` 而非 `peerDependencies`
（业务包声明 `react` 为 peer，由本包满足）。

## 启动编排（`src/boot/`）

- `preload.ts` —— `preloadAppHome()`：Server 就绪后拉 Agent 目录 + 账号 + 最近会话；
  `ensureDiscoveryScanned()`：进首页前的兜底。
- `boot-gate.tsx` —— `<BootGate>`：预载完成前不挂路由（HTML 启动屏继续挡着）。
- `alert-navigator.ts` —— 把 `router.navigate` 注入 `@v2/runtime/app-alert`，
  让告警里的操作按钮能走 SPA 路由（本应用是 `createHashRouter`，整页跳转会丢路由）。

**为什么编排在这里而不是 `@v2/runtime`**：它要组合 Agent 域与账号域，两个域互不引用；
放在基座包里等于让 `runtime` 反向依赖业务包。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
