# Recipe: Add Sidebar Page

> UI 结构与视觉：先读 [../guides/ui-reference.md](../guides/ui-reference.md)（Shadcn Admin + Aceternity UI）。

## 修改顺序

1. `features/<feature>/pages/<page>.tsx` — 骨架组件
2. `features/<feature>/index.ts` — 注册 sidebar 元数据
3. `apps/desktop/src/route/index.ts` — 聚合（待 router）
4. 仅用 `packages/ui` 组件

## 禁止

- 页面内 invoke / 业务逻辑
- 跨 feature import 组件

## Checklist

- [ ] 无 @tauri-apps/api
- [ ] 布局用 ui 包

## 模板

[../templates/feature/](../templates/feature/)
