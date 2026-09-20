# packages/client/ui-theme

设计令牌与全局样式。**唯一允许出现字面颜色值的地方。**

```text
src/index.css       Tailwind v4 入口（@import "tailwindcss" + @theme + 全局基线）
src/tokens.css      语义令牌：--bg / --text / --accent / --radius …
src/scrollbar.css   滚动条
```

## 为什么单独成包

业务组件里一旦出现 `#3b82f6` 或 `oklch(...)`，主题就再也改不动了。把令牌收进独立包后，
「这个颜色是哪来的」只有一个答案。业务包只允许通过 `var(--token)` 或 Tailwind 的语义类
（`bg-bg-panel`、`text-text-muted`）消费。

## 边界

- 只放 CSS 与令牌定义，**不放组件、不放 TS 逻辑**。
- 不 import 任何其他前端包（它是依赖图的根）。
- 业务包**不要**往这里加组件专属样式；那是各业务包自己的事。

## Tailwind v4 的内容扫描（改结构时必看）

Tailwind 默认从 Vite 项目根自动扫描源文件。本项目 Vite 根是**仓库根**，而组件已移入
`packages/`，故 `src/index.css` 里显式声明了 `@source`，不依赖自动探测的启发式：

```css
@source "../../../../packages";
@source "../../../../apps";
```

`@source` 的路径**相对于 CSS 文件自身**（`packages/client/ui-theme/src/` 上溯四级到仓库根）。
新增一级包目录时，记得回来补一行 —— 漏了不会报错，只会让 Tailwind 悄悄不生成那些类。

## shadcn 组件的语义变量桥接

`ui-primitives` 的组件读的是 shadcn 那套变量（`--primary` / `--muted` / `--ring` …），
项目自己的令牌在 `tokens.css`。`index.css` 里有一段**不带 `@layer` 的裸 `:root`** 专门做别名，
把前者指向后者 —— 不要给这段加 `@layer`，也不要把 shadcn 的组件变量值写进 `tokens.css`。

两个已定的让步，改之前先读：

- `--accent` 归 shadcn（组件内部硬编码 `hover:bg-accent`，必须是浅色悬停面）。
  项目原先那个深色 `#353535` 语义现在由 `--selected` 承担，业务用 `bg-selected/30`。
- 圆角刻度直接写字面值（`sm 4px / md 8px / lg 12px`）而不是 `var(--radius-sm)`：
  后者在 `@theme` 里是循环引用，Tailwind 会静默丢弃整条声明。

以后 `shadcn add` 新组件若带进新令牌，回 `index.css` 把它们也指到项目令牌上，不要引入新的字面值。
