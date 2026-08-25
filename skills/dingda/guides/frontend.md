# Frontend Guide（React / TypeScript）

适用范围：`apps/desktop/src/**`、`packages/ui/**`、`packages/platform/**`、`packages/store/**`

## 必须技术栈

| 类别 | 库 |
|------|-----|
| 编译 | **React Compiler**（`babel-plugin-react-compiler`） |
| UI | **shadcn/ui + Radix UI**（组件只在 `packages/ui`） |
| 状态 | **Zustand**（经 `@desk/store`） |
| 样式 | **Tailwind CSS**（令牌在 `@desk/ui/tokens`） |
| 动画 | **Motion** + Spring 预设 |
| 图标 | **Lucide React** |
| 表格 | **shadcn Table + TanStack Table + TanStack Query**（`DataTable`） |
| 虚拟列表 | **TanStack Virtual** |
| 表单 | **FormInput → Input → React Hook Form → Zod** |
| 服务端状态 | **TanStack Query**（`QueryProvider` / `useQuery`） |
| 日期 | **date-fns** |
| 主题 | **next-themes** |
| 拖拽 | **dnd-kit** |
| 命令面板 | **cmdk** |
| Toast | **Sonner** |

详见 [ui-design-system.md](ui-design-system.md)。

## UI 参考（强制 — 写 UI 前必读）

**任何 UI 任务先读** [ui-reference.md](ui-reference.md)：

- **Shadcn Admin** — Layout / Sidebar / Header 结构参考（增量迁移，禁止整库覆盖）
- **@desk/ui shadcn** — Table / Form / Dialog 等业务组件
- **Aceternity UI** — `packages/ui/src/components/aceternity/` 视觉增强层

完整规格：[docs/shadcn-admin-aceternity-migration-prompt.md](../../../docs/shadcn-admin-aceternity-migration-prompt.md)

## 设计工程 Skill（强制）

UI / 动效必须遵循 Emil Kowalski Skill（`npx skills add emilkowalski/skill`）：

1. 改 UI 前阅读 [`.cursor/skills/emil-design-eng/SKILL.md`](../../.cursor/skills/emil-design-eng/SKILL.md)
2. 动效审查用 [`.cursor/skills/review-animations/SKILL.md`](../../.cursor/skills/review-animations/SKILL.md)
3. 动效词表 / 找机会 / 改进：`animation-vocabulary` · `find-animation-opportunities` · `improve-animations`
4. Apple HIG 参考：`apple-design`（与本仓库 Apple 风令牌一起用）

摘要：UI 动效通常低于 300ms、ease-out、只动 transform/opacity、无 scale(0)、高频少动、`prefers-reduced-motion`、审查用 Before/After/Why 表。

自检：Agent 对话执行 `/check-emil-design`（可跟路径或「当前 diff」）。

## 样式规则（硬约束）

Feature 层 **禁止** 裸 Tailwind 原子类：

```tsx
// ❌
<div className="bg-white rounded-lg backdrop-blur-xl" />

// ✅
import { Card } from "@desk/ui";
<Card variant="glass" />
```

`packages/ui` 内部用 Tailwind 组装 `variant`；对外只暴露组件 API。

## Apple 风令牌

Glass · Blur · Backdrop · Motion · Spring · Dynamic Color · Radius · Typography

定义于 `packages/ui/src/tokens/`，通过 CSS 变量与 `spring` 预设导出。

## 职责

| 负责 | 禁止 |
|------|------|
| UI · 交互 · 主题 · 布局 · 动画 | 业务规则 · SQL · AI 逻辑 |
| 组合 `@desk/ui` 组件 | Feature 裸 Tailwind / 直接 Radix |
| Feature 本地状态经 `@desk/store` | 在 `@desk/store` 包内写业务领域 store |
| 通过 platform 调 Rust | `@tauri-apps/api`（Feature 层） |

## 目录约定

```
apps/desktop/src/
├── app/              # 根组件、窗口壳、设置弹窗、401/503
├── components/       # 跨 Feature 共享组合
├── license/          # 授权闸门与激活组件
├── lifecycle/        # 启动 / 错误 / 插件生命周期
├── route/
└── features/<name>/  # 业务 Feature 页面

packages/ui/src/      # 通用 UI
packages/store/src/   # Zustand 底座（createDeskStore）
packages/platform/src/# IPC / OS
```

## Store

```typescript
import { createDeskStore } from "@desk/store";

export const chatStore = createDeskStore<ChatState>((set) => ({
  // Feature 内定义状态与 actions
}));
```

命名：`chatStore`、`userStore`。业务状态放 Feature / 壳层，不放 `@desk/store` 包本体。

## IPC

```typescript
import { ipc } from "@desk/platform/ipc";
// Feature 禁止 invoke() / @tauri-apps/api
```

## shadcn 组件添加

```bash
cd packages/ui && pnpm dlx shadcn@latest add button
```

## Lint

```bash
pnpm lint:frontend
```

## 布局与页面骨架

M5 UI Shell：窗口壳全部在 `apps/desktop`；`@desk/ui` 只提供通用控件与页面原语。

```
apps/desktop
├─ TitleBar（唯一窗口 header：logo + TabBar + 窗口控制）
└─ AppLayout
   ├─ NavRail
   └─ MainPanel
      └─ PageScaffold（@desk/ui）/ Feature 内容
```

| 组件 | 包 | 用途 |
|------|-----|------|
| `TitleBar` / `AppLayout` / `NavRail` / `MainPanel` / `TabBar` | `apps/desktop/src/app` | 桌面窗口壳与工作区装配 |
| `ThemeToggle` / `IconButton` / `Button` / `Card` | `@desk/ui` | 通用交互与展示控件 |
| `PageScaffold` / `PageContainer` | `@desk/ui` | Feature 页面统一内边距、宽度，以及 ScrollArea 滚动 |
| `nav-registry.ts` | `apps/desktop` | 聚合各 Feature 的 `navItem` |
| `page-meta.ts` | `apps/desktop` | 路由 → 页面标题映射（中文文案） |

约定：`@desk/ui` 只放 Button / Card / Input 等通用组件；DingDa 窗口壳、NavRail、工作区 Tab 放 `apps/desktop`。

新增 Feature 前端骨架：

1. `features/<name>/index.ts` 导出 `{ id, path, navItem }` 与 page 组件
2. 在 `route/nav-registry.ts` 注册 `navItem`
3. 在 `route/router.tsx` 添加路由
4. 在 `route/page-meta.ts` 添加标题（可选 description）
5. 页面内容用 `PageScaffold` 包裹；占位页可复用 `FeaturePlaceholderPage`

## 相关

- [ui-reference.md](ui-reference.md) — **UI 参考首选**
- [ui-design-system.md](ui-design-system.md)
- [ipc.md](ipc.md)
- [../../packages/ui/README.md](../../packages/ui/README.md)
