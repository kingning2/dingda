# @desk/ui

DingDa 设计系统与 **通用** UI 组件库。Feature 层的视觉与交互原语**必须**从此包导出。

> Feature 层禁止裸用 `bg-white`、`rounded-lg` 等 Tailwind 原子类；使用语义组件与 variant。

**UI 参考首选：** [skills/dingda/guides/ui-reference.md](../skills/dingda/guides/ui-reference.md)（Shadcn Admin 结构 + shadcn 组件 + Aceternity 视觉层）。

## 边界

| 放在 `@desk/ui` | 不放在 `@desk/ui` |
|-----------------|-------------------|
| Button / Input / Select / Card / ScrollArea | 窗口 TitleBar |
| IconButton / ThemeToggle / Toaster | NavRail / AppLayout / MainPanel |
| PageScaffold / PageContainer / PageGlowCard | 工作区 TabBar |
| `components/aceternity/` · `components/effects/` | 任何 DingDa 桌面壳装配 |
| DataTable / Form / FormInput / QueryProvider | IPC / 业务请求 |

桌面窗口壳在 `apps/desktop/src/app/`。

## 技术栈

| 能力 | 库 |
|------|-----|
| 组件 | shadcn/ui + Radix UI |
| 样式 | Tailwind CSS（令牌在 `src/tokens/`） |
| 动画 | Motion（Spring） |
| 图标 | Lucide React |
| 表格 | shadcn Table + TanStack Table + TanStack Query（`DataTable`） |
| 虚拟列表 | TanStack Virtual |
| 表单 | FormInput → Input → React Hook Form → Zod |
| 服务端状态 | TanStack Query（`QueryProvider`） |
| 日期 | date-fns |
| 主题 | next-themes |
| 拖拽 | dnd-kit |
| 命令面板 | cmdk |
| Toast | Sonner |

## Apple 风令牌

| 令牌 | CSS 变量前缀 | 用途 |
|------|--------------|------|
| Glass | `--glass-*` | 半透明材质 |
| Blur | `--blur-*` | 模糊强度 |
| Backdrop | `--backdrop-*` | 背景遮罩 |
| Motion | `--motion-*` | 时长 / 缓动 |
| Spring | `spring.*` in `tokens/motion.ts` | Motion spring 预设 |
| Dynamic Color | `--color-*` | 语义色（非 hex 硬编码） |
| Radius | `--radius-*` | 圆角 |
| Typography | `--font-*` / `--text-*` | 字体阶梯 |

## 使用

桌面端 `globals.css` 必须扫描本包源码，否则组件类不会进入最终 CSS：

```css
@import "tailwindcss";
@import "@desk/ui/tokens";

@source "../../../../packages/ui/src/**/*.{ts,tsx}";
@source "../**/*.{ts,tsx}";
```

```tsx
import { DataTable, Form, FormInput, useQuery, z } from "@desk/ui";

const schema = z.object({
  name: z.string().min(1, "必填"),
});

export function Page() {
  const query = useQuery({
    queryKey: ["items"],
    queryFn: fetchItems, // Feature 注入 IPC；@desk/ui 不发请求
  });

  return (
    <>
      <DataTable columns={columns} query={query} />
      <Form schema={schema} onSubmit={save}>
        <FormInput name="name" label="名称" />
      </Form>
    </>
  );
}
```

`QueryProvider` 在桌面根挂一次（`apps/desktop/src/app/app.tsx`）。

## 目录

```
src/
├── tokens/          # 设计令牌（CSS 变量 + Motion spring）
├── lib/             # cn() 等工具
├── query/           # QueryProvider（TanStack Query）
├── theme/           # ThemeProvider（next-themes）
├── motion/          # 可复用动效原语
└── components/      # shadcn 风格通用组件（variant 驱动）
    ├── aceternity/  # Aceternity 视觉封装（Dashboard / AI 等）
    ├── effects/     # GlowingEffect / AmbientSpotlight
    ├── data-table.tsx
    ├── form.tsx
    └── layout/      # PageContainer / PageScaffold / Sidebar
```

## 禁止

- IPC / 业务状态 / API 调用
- 窗口壳 / 工作区导航等仅 desktop 可用的页面级组件
- 在 Feature 中复制本包 Tailwind 类名

## shadcn 初始化

组件通过 shadcn CLI 添加到本包（`components.json`），而非 `apps/desktop`。

```bash
cd packages/ui && pnpm dlx shadcn@latest add button
```
