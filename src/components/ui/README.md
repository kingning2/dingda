# UI 组件（shadcn/ui）

本项目使用 [shadcn/ui](https://ui.shadcn.com/)（`base-nova` 风格，Tailwind v4 + Base UI）。

## 原则

- **禁止在业务代码里裸用原生标签**（`<button>`、`<input>`、`<textarea>` 等），统一走 `@/components/ui/*`
- 布局壳（`components/layout/`）和页面（`pages/`）只组合 shadcn 组件 + Tailwind
- 工具函数 `cn()` 从 `@/lib/utils` 引入

## 已安装组件

| 组件 | 路径 | 典型用途 |
|------|------|----------|
| `Button` | `ui/button.tsx` | 所有可点击操作 |
| `Input` | `ui/input.tsx` | 单行输入、搜索框 |
| `Textarea` | `ui/textarea.tsx` | 多行输入（首页 Composer） |
| `Dialog` | `ui/dialog.tsx` | 弹层（搜索、确认） |
| `Card` | `ui/card.tsx` | 项目卡片、占位页 |
| `Badge` | `ui/badge.tsx` | 状态标签 |
| `DropdownMenu` | `ui/dropdown-menu.tsx` | 账号菜单、更多操作 |
| `Avatar` | `ui/avatar.tsx` | 用户头像 |
| `Separator` | `ui/separator.tsx` | 分割线 |
| `ScrollArea` | `ui/scroll-area.tsx` | 可滚动区域 |
| `Kbd` | `ui/kbd.tsx` | 快捷键提示 |
| `Tooltip` | `ui/tooltip.tsx` | 悬停说明 |
| `Command` | `ui/command.tsx` | 命令面板（搜索） |

## 新增组件

```bash
npx shadcn@latest add <component-name>
```

配置见项目根目录 `components.json`。

## 使用示例

```tsx
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

<Button variant="outline" size="sm">取消</Button>
<Button>确定</Button>

<Dialog open={open} onOpenChange={setOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>搜索项目</DialogTitle>
    </DialogHeader>
    <Input placeholder="输入关键词…" />
  </DialogContent>
</Dialog>
```

## 全局 Provider

`App.tsx` 根节点已包裹 `TooltipProvider`，使用 `Tooltip` 的组件无需重复添加。

## 全局滚动条

样式在 `src/styles/scrollbar.css`：细圆角滑块、透明轨道，已全局替换系统滚动条。令牌 `--scrollbar-thumb` 定义在 `tokens.css`。
