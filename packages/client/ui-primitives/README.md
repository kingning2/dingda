# packages/client/ui-primitives

无业务的原子组件。绝大多数由 shadcn CLI 生成（`radix-nova` 风格，Tailwind v4 + Radix UI），
少数几个是**手写组合件**（见下）。外加一个 `cn()` 工具。

```text
button / input / textarea / select / dialog / dropdown-menu / tabs / tooltip /
card / badge / avatar / separator / scroll-area / kbd / command / alert /
input-group

form-field.tsx      标签 + 控件 + 说明的字段排版（手写）
stat-tile.tsx       指标块：一个名称配一个值（手写）
utils.ts            cn() —— clsx + tailwind-merge
```

## 为什么单独成包

这层**没有业务**：给它们任何 props 都能正确渲染，不知道账号、采集、Agent 是什么。
独立成包后，「这个按钮为什么长这样」的答案只在这一个目录里；而且它可以直接被替换
（换主题库、换组件库）而不动任何业务代码。

## 边界

- **不放业务判断**：不读全局状态、不发请求、不 import 任何业务包或 `contracts`。
- 只依赖 `radix-ui` / `cva` / `clsx` / `cmdk` / `lucide-react` / `tailwind-merge`。
- 依赖方向：`ui-primitives` 被所有业务包依赖，它自己不依赖任何业务包。
- 颜色只走令牌（`var(--token)` 或语义类），不写字面值 —— 令牌在 [`ui-theme`](../ui-theme/README.md)。

## 手写组合件

`form-field` 与 `stat-tile` 不是 CLI 产物，是照着业务里逐字重复了十几遍的排版手写的。
放在这里的原因和 CLI 产物一样：零业务、零状态，给什么渲染什么。

- **`form-field`** —— 「标签在上、控件居中、说明在下」。shadcn 的对应物是 `form`
  （`FormItem` / `FormLabel` / `FormMessage`），但它要连带引入 react-hook-form 与 zod，
  为这点排版重复不值。三条约定：
  - 标签与控件是**兄弟**节点，不是 `<label>` 包住控件 —— Radix `Select` 的 trigger 是个
    button，`<label>` 包住它关联不上，属于无效标记。所以传了 `htmlFor` 才渲染真 `<label>`
    （也就才有「点标签聚焦输入框」），`<Select>` 那侧不传。
  - `hint` 收节点而不只是字符串，说明区自身是 `flex flex-col gap-1.5`，多行说明的行距
    与「控件 ↔ 说明」的间距一致；每行若要各自的语气（如「拉取失败」行单独走危险色），
    由调用方在行内自己挂色 —— 这也是 `tone` 只作用于整块的原因。
  - `actions` 是标签行右侧的动作区（如「重新获取」）。
- **`stat-tile`** —— 一个名称配一个值，渲染的是 `<dt>` / `<dd>`，**必须放在 `<dl>` 里**。

业务包用它们时**不要加业务 props**：需要业务知识，就说明那段该留在业务包里，
而不是往这里塞。

## 新增组件

```bash
npx shadcn@latest add <component-name>
```

`components.json` 的 `aliases.ui` 已指向本包，CLI 会直接把文件写进 `src/`。
新增后 `package.json` 的 `exports` 是通配 `./*`，无需登记。

CLI 落盘后**务必过一眼产物**，有两处它在本仓不按预期工作：

- 会生成 `src/index.ts/<name>.tsx` 这种把 `index.ts` 当目录的路径 —— 根 `tsconfig.json`
  里 `@v2/ui-primitives` 是**非通配**路径，CLI 把组件名缀在了文件路径后面。
  把里面的 `.tsx` 移上来、删掉那个目录即可。
- 不会把 `import { cn } from "cn"` 改写成 `from "./utils"`（因为根 `package.json` 里
  `cn` 是个真依赖），且新组件若引用了同包其他组件会写成 `@v2/ui-primitives/xxx` ——
  两者都得手工换成相对路径，否则 `scripts/check-workspace-deps.mjs` 会硬失败。

## 用法

```tsx
import { Button } from "@v2/ui-primitives/button";
import { cn } from "@v2/ui-primitives/utils";
```

**业务代码禁止裸用原生标签**（`<button>` / `<input>` / `<textarea>`），统一走本包。
