# Layout 骨架说明

本目录实现 **OpenDesign 风格** 的页面外壳布局。UI 组件统一使用 **shadcn/ui**（`@/components/ui/*`），见 [`../ui/README.md`](../ui/README.md)。

---

## 页面是怎么拼出来的

从外到内一共 **五层**（Tauri 标题栏 + 工作区壳 + 页面内容）：

```
App (src/App.tsx)
└── TooltipProvider
    └── AppShell                    ← Tauri 标题栏（TitleBar）
        └── WorkspaceShell          ← 工作区主体（当前无 Tab 顶栏）
            └── EntryShell          ← 左栏 + 主内容
                ├── EntryNavRail
                └── {children}
```

> **WorkspaceTabsBar**（原红框区域）在只有入口页时与侧栏导航重复，已移除。
> 打开多个项目 Tab 时再接入 `workspace-tabs-bar.tsx`。

---

## 各文件职责

| 文件 | 职责 | 主要 shadcn 组件 |
|------|------|------------------|
| `workspace-shell.tsx` | 工作区主体容器 | — |
| `workspace-tabs-bar.tsx` | （预留）多项目 Tab 顶栏 | `Button`, `Separator` |
| `entry-shell.tsx` | 左栏 + 主内容；搜索弹层；收起后展开按钮 | `Dialog`, `Input`, `Button` |
| `entry-nav-rail.tsx` | 左侧导航 | `Button`, `DropdownMenu`, `Avatar`, `Kbd` |

**不在本目录、但参与拼装：**

| 位置 | 职责 |
|------|------|
| `components/app-shell.tsx` | Tauri 无边框窗口 + `TitleBar` |
| `components/home/*` | 首页：`Card`, `Textarea`, `Button`, `Badge` |
| `pages/*` | 各入口视图页面 |
| `App.tsx` | 路由、`railOpen` 状态、拼装各层壳 |

---

## 路由与内容切换

路由在 `src/lib/router.ts`（hash 路由）：

| Hash | 页面组件 |
|------|----------|
| `#` / 空 | `HomeView` |
| `#/projects` | `ProjectsPage` |
| `#/community` | `CommunityPage` |
| `#/plugins` | `PluginsPage` |
| `#/design-systems` | `DesignSystemsPage` |

`App.tsx` 中 `railOpen` 同时传给 `WorkspaceTabsBar` 和 `EntryShell`，保证顶栏与侧栏状态一致。

---

## 样式

- **shadcn 主题变量**：`src/styles/index.css`
- **OpenDesign 布局令牌**：`src/styles/tokens.css`
- **全局滚动条**：`src/styles/scrollbar.css`（细圆角滑块，非系统默认）

---

## 新增入口页

1. `pages/` 添加页面（使用 `Card`、`Button` 等）
2. `router.ts` 添加 `EntryView`
3. `App.tsx` 的 `EntryContent` 添加分支
4. `mock-data.ts` 的 `NAV_ITEMS` 添加导航项

---

## 本地预览

```bash
pnpm dev
```
