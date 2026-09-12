# Layout 骨架说明

本目录实现 **OpenDesign 风格** 的页面外壳布局。原子组件来自
[`@v2/ui-primitives`](../ui-primitives/README.md)，设计令牌来自
[`@v2/ui-theme`](../ui-theme/README.md)。

---

## 页面是怎么拼出来的

从外到内（Tauri 标题栏 → 工作区壳 → 入口壳 → 页面内容）：

```text
main.tsx
└── App.tsx                                   （apps/web/src/App.tsx）
    └── ServerProvider                        @v2/runtime      订阅 Server 状态、注入 baseUrl
        └── BootGate                          apps/web/src/boot 预载完成前不挂路由
            └── TooltipProvider               @v2/ui-primitives
                ├── RouterProvider → router   createHashRouter
                │   └── AppLayout             apps/web/src/routes/layouts
                │       └── AppShell          ← Tauri 标题栏（TitleBar）
                │           └── WorkspaceLayout
                │               └── WorkspaceShell
                │                   └── EntryLayout
                │                       └── EntryShell   ← 左栏 + 主内容
                │                           ├── EntryNavRail
                │                           ├── PageHeader （有 handle.title 时）
                │                           └── AnimatedOutlet  ← 页面切换动效
                └── AppAlertHost              @v2/ui-feedback
```

外壳只负责**骨架与出口**：路由表、页面组件、`railOpen` 状态都在
[`apps/web`](../../../../apps/web/README.md)。外壳不认识任何业务域页面。

> **WorkspaceTabsBar**（多项目 Tab 顶栏）仍是预留件。只有入口页时它与侧栏导航重复，
> 所以当前 `WorkspaceShell` 不渲染它；打开多项目 Tab 时再接入。

---

## 各文件职责

| 文件 | 职责 | 用到的原子组件 |
|------|------|----------------|
| `app-shell.tsx` | Tauri 无边框窗口 + `TitleBar`，订阅最大化状态 | — |
| `title-bar.tsx` | 自绘标题栏：拖拽区 + 最小化/最大化/关闭 | `Button` |
| `workspace-shell.tsx` | 工作区主体容器（纯布局） | — |
| `workspace-tabs-bar.tsx` | （预留）多项目 Tab 顶栏 | `Button`, `Separator` |
| `entry-shell.tsx` | 左栏 + 主内容；搜索弹层；全宽模式 | `Dialog`, `Input` |
| `entry-nav-rail.tsx` | 左侧导航 | `Button`, `DropdownMenu`, `Avatar`, `Kbd` |
| `page-header.tsx` | 由路由 `handle.title` 注入的页面标题 | — |
| `animated-outlet.tsx` | 内容区出口，切换时淡入位移 | — |
| `route-transition.ts` | `AnimatedOutlet` 的动效参数（含 reduced-motion 分支） | — |

**为什么 `AnimatedOutlet` 在本包而不在应用**：它就是 `EntryShell` 内容区的渲染实现。
放在应用里会让本包反过来 `import "@web/routes/animated-outlet"` —— 包依赖应用，
方向是反的。所以连 `route-transition.ts` 一起挪进来（它是前者的私有参数集）。

---

## 路由与内容切换

路由表在 [`apps/web/src/routes/router.tsx`](../../../../apps/web/src/routes/router.tsx)，
路径常量在 [`@v2/routes/paths`](../routes/README.md)。

| Hash | 页面 | 标题来源 |
|------|------|----------|
| `#/` | `HomeRoute` | — |
| `#/projects` | `ProjectsRoute` | `handle.title` |
| `#/plugins` | `PluginsPage` | `handle.title` |
| `#/agents` | `AgentsPage` | `handle.title` |
| `#/accounts` | `AccountsPage` | `handle.title` |
| `#/assets` | `AssetsPage` | — |
| `#/integrations` | `IntegrationsPage` | — |
| `#/crawler` | `CrawlerPage` | `handle.title` |
| `#/work/:workId` | `WorkRoute` | `handle.fullBleed`（不渲染侧栏） |

`EntryLayout` 读 `useMatches()` 取出 `handle`，把标题与 `fullBleed` 传给 `EntryShell`。

---

## 样式

设计令牌与全局样式**不在本包**，全部在 [`@v2/ui-theme`](../ui-theme/README.md)：

- Tailwind 入口与主题变量：`ui-theme/src/index.css`
- OpenDesign 布局令牌：`ui-theme/src/tokens.css`
- 全局滚动条：`ui-theme/src/scrollbar.css`

本包只用 Tailwind 类名与 `cn()`（来自 `@v2/ui-primitives/utils`）。

---

## 新增一个入口页

1. `apps/web/src/pages/` 加页面组件
2. `apps/web/src/routes/router.tsx` 加一条路由，`handle: entry("标题")`
3. `@v2/routes/paths` 加路径常量（如果要在别处引用）
4. 导航项在 `@v2/ui-home/mock-data` 的 `NAV_ITEMS` 里补一行 —— 侧栏读的是它，
   不是本包内的常量（本包只负责渲染，不认识导航内容）

---

## 本地预览

```bash
pnpm dev        # 仓库根；会先跑依赖卫生检查
```
