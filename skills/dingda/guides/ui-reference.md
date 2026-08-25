# UI 参考体系（Shadcn Admin + Aceternity UI）

> **任何 UI 设计、改版、新页面或组件选型，必须先对照本指南，再写代码。**

DingDa 是 **Tauri 桌面端** 企业 AI 电商中台，不是普通 Web Admin。视觉与结构遵循三层组合，**三者互补、不可互相替代**：

```text
Shadcn Admin          →  中台 Layout / Sidebar / Header / 页面结构（参考与增量迁移目标）
shadcn/ui (@desk/ui)  →  Table / Form / Dialog / Select 等业务基础组件
Aceternity UI         →  Dashboard / AI 页视觉增强、Spotlight / Bento / 光晕 / 微交互
```

完整改造规格见 [`docs/shadcn-admin-aceternity-migration-prompt.md`](../../../docs/shadcn-admin-aceternity-migration-prompt.md)。

---

## 读文档顺序（Agent / 开发者）

做 UI 相关任务时，按序读取，够用即停：

1. **本文件** — 三层职责与页面优先级
2. [`ui-design-system.md`](ui-design-system.md) — 令牌、禁止裸 Tailwind、Emil 动效约束
3. [`docs/shadcn-admin-aceternity-migration-prompt.md`](../../../docs/shadcn-admin-aceternity-migration-prompt.md) — 路由清单、分页面改造指引、禁止事项
4. [`.cursor/skills/emil-design-eng/SKILL.md`](../../../.cursor/skills/emil-design-eng/SKILL.md) — 动效细节（写 UI 前必读）

外部参考（结构灵感，**禁止整库覆盖**）：

- [Shadcn Admin](https://github.com/satnaing/shadcn-admin) — Layout、Sidebar、Header、Admin UX 组织
- [Aceternity UI](https://ui.aceternity.com) — Spotlight、Bento、Moving Border、背景与卡片动效

---

## 仓库内落地位置

| 层级 | 路径 | 职责 |
|------|------|------|
| 桌面壳 | `apps/desktop/src/app/` | TitleBar、AppLayout、WorkspaceSidebar、MainPanel |
| 页面骨架 | `packages/ui/src/components/layout/` | PageScaffold、PageHeader、Sidebar、PageGlowCard |
| shadcn 基础 | `packages/ui/src/components/` | Button、Table、Form、Dialog、DataTable… |
| Aceternity 封装 | `packages/ui/src/components/aceternity/` | AnimatedStatCard、BentoGrid、SpotlightCard、PageBackground |
| 已有动效 | `packages/ui/src/components/effects/` | GlowingEffect、AmbientSpotlight |
| 业务页 | `apps/desktop/src/features/` | 组合上述层，**不写 Aceternity 原始代码堆在 Feature 里** |

---

## 页面改造优先级

| 优先级 | 场景 | Aceternity 用法 |
|--------|------|-----------------|
| **P0** | Dashboard、AI 配置、Agent | Spotlight 背景、Bento、AnimatedStatCard、配置卡片 Hover |
| **P1** | Chat、Monitor、Discovery | Chat → [inbox-1](https://shadcnblocks-admin.vercel.app/project-management/inbox-1)；Monitor 列表 → [project-list-1](https://shadcnblocks-admin.vercel.app/project-management/project-list-1)，详情 → [project-detail-2](https://shadcnblocks-admin.vercel.app/project-management/project-detail-2) |
| **P1 克制** | accounts / items / orders / search | 以 shadcn Table / Form 为主，不强行加额外装饰动画 |
| **P2** | 详情页、Knowledge | PageScaffold 统一；Knowledge 导航待产品确认 |

`PageScaffold` 默认 `ambient="spotlight"`，工作区页面统一开启动态聚光灯背景；仅在不需要光效时显式传 `none`。

---

## 必须遵守

1. **先参考 Shadcn Admin 结构，再实现** — 增量迁移到现有 `WorkspaceSidebar` / `PageScaffold`，禁止整项目覆盖
2. **基础交互只用 `@desk/ui` shadcn 组件** — 不重复实现 Button / Table / Form
3. **Aceternity 必须实际使用** — 通过 `aceternity/` 封装层调用，不是只保留 dead code
4. **不删除已有 Aceternity** — Sidebar、GlowingEffect、PageGlowCard 等保留并复用
5. **动效服务于信息层级** — 150–300ms，尊重 `prefers-reduced-motion`（见 emil-design-eng）
6. **业务逻辑不进 UI 封装层** — IPC、Store 留在 `features/`

---

## 禁止

- 用 Shadcn Admin **整库替换**现有 UI
- 为 Aceternity 重写 Table / Form / Dialog
- 所有页面都做成传统 Admin（满屏 Card + Table）
- 每页堆大量无意义动画
- 破坏编译期平台裁剪（`@platform-routes` / `managePath`）
- 修改 IPC 契约（除非任务明确要求）

---

## 相关

- [frontend.md](frontend.md)
- [ui-design-system.md](ui-design-system.md)
- [../../packages/ui/README.md](../../packages/ui/README.md)
- [../recipes/add-sidebar-page.md](../recipes/add-sidebar-page.md)
