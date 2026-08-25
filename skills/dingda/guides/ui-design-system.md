# UI Design System

DingDa 采用 **Modern SaaS + AI Platform + Enterprise Admin** 视觉语言（Apple 风令牌 + Shadcn Admin 结构 + Aceternity 增强），全部封装在 `@desk/ui`。

> **做 UI 前先读** [`ui-reference.md`](ui-reference.md) — Shadcn Admin + Aceternity UI 参考体系与页面优先级。

## 核心原则

1. **语义组件优先** — Feature 只组合 `@desk/ui`，不写原子 Tailwind
2. **Variant 驱动** — `variant="glass"` 而非复制 class 字符串
3. **令牌单一来源** — 颜色 / 圆角 / 模糊 / 动画来自 `packages/ui/src/tokens/`
4. **React Compiler** — 自动 memo，减少手写优化

## 禁止 vs 必须

```tsx
// ❌ apps/desktop/src/features/** 中禁止
<div className="bg-white dark:bg-zinc-900 rounded-lg border p-4 backdrop-blur-md" />

// ✅ 必须
import { Card } from "@desk/ui";
<Card variant="glass" padding="md">...</Card>
```

`packages/ui` 内部**可以**使用 Tailwind utility 组装 variant，但对外暴露组件 API。

## 技术映射

| 需求 | 封装位置 |
|------|----------|
| Layout / Sidebar / 页头结构 | 参考 Shadcn Admin → 落地 `apps/desktop/src/app/layout` + `@desk/ui/layout` |
| Dashboard KPI / Bento / Spotlight | `@desk/ui` `components/aceternity/` |
| 光晕边框 / 聚光灯背景 | `@desk/ui` `effects/` + `aceternity/` |
| 按钮 / 输入 / 对话框 | `@desk/ui` shadcn + Radix |
| 毛玻璃卡片 | `Card variant="glass"` / `PageGlowCard` |
| 页面过渡 | `motion` + `spring.default` |
| 深色模式 | `ThemeProvider`（next-themes） |
| 数据表 | `DataTable`（shadcn Table + TanStack Table + 可选 Query） |
| 长列表 | `VirtualList`（TanStack Virtual） |
| 表单校验 | `Form` + `FormInput`（RHF + Zod） |
| 服务端缓存 | `QueryProvider` / `useQuery`（Feature 注入 IPC `queryFn`） |
| 日期显示 | `format` from date-fns via ui helpers |
| 拖拽排序 | `Sortable`（dnd-kit） |
| ⌘K 面板 | `Command`（cmdk） |
| 通知 | `toast` / `Toaster`（Sonner） |

## Glass 示例

```tsx
<Card variant="glass">
  <CardHeader>
    <CardTitle>智能客服</CardTitle>
  </CardHeader>
  <CardContent>...</CardContent>
</Card>
```

对应令牌（`tokens/index.css`）：

```css
--glass-bg: oklch(1 0 0 / 0.55);
--glass-blur: 24px;
--glass-border: oklch(1 0 0 / 0.18);
--glass-shadow: 0 8px 32px oklch(0 0 0 / 0.12);
```

## Motion / Spring

动效决策与审查须遵循 [emil-design-eng](../../.cursor/skills/emil-design-eng/SKILL.md) /
[review-animations](../../.cursor/skills/review-animations/SKILL.md)（低于 300ms、ease-out、仅 transform/opacity 等）。

```tsx
import { motion } from "motion/react";
import { spring } from "@desk/ui/tokens/motion";

<motion.div transition={spring.snappy} />
```

## 相关

- [ui-reference.md](ui-reference.md) — **UI 参考首选**
- [../../../docs/shadcn-admin-aceternity-migration-prompt.md](../../../docs/shadcn-admin-aceternity-migration-prompt.md)
- [frontend.md](frontend.md)
- [../../packages/ui/README.md](../../packages/ui/README.md)
- [../../.cursor/skills/emil-design-eng/SKILL.md](../../.cursor/skills/emil-design-eng/SKILL.md)
