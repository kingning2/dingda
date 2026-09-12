# packages/client/ui-layout

窗口骨架：应用外壳、标题栏、导航栏、主区域布局。

包名 `@v2/ui-layout`。

## 文件

- `src/README.md`
- `src/app-shell.tsx`
- `src/entry-nav-rail.tsx`
- `src/entry-shell.tsx`
- `src/page-header.tsx`
- `src/title-bar.tsx`
- `src/workspace-shell.tsx`
- `src/workspace-tabs-bar.tsx`

## 依赖

- 工作区：@v2/routes / @v2/runtime / @v2/ui-home / @v2/ui-primitives
- 外部：lucide-react / react-router-dom
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
