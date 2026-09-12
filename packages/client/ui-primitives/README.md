# packages/client/ui-primitives

无业务的原子组件，全部由 shadcn CLI 生成（`base-nova` 风格，Tailwind v4 + Base UI）。
外加一个 `cn()` 工具。

```text
button / input / textarea / select / dialog / dropdown-menu / tabs / tooltip /
card / badge / avatar / separator / scroll-area / kbd / command / alert /
input-group
utils.ts            cn() —— clsx + tailwind-merge
```

## 为什么单独成包

这层**没有业务**：给它们任何 props 都能正确渲染，不知道账号、采集、Agent 是什么。
独立成包后，「这个按钮为什么长这样」的答案只在这一个目录里；而且它可以直接被替换
（换主题库、换组件库）而不动任何业务代码。

## 边界

- **不放业务判断**：不读全局状态、不发请求、不 import 任何业务包或 `contracts`。
- 只依赖 `@base-ui/react` / `cva` / `clsx` / `cmdk` / `lucide-react` / `tailwind-merge`。
- 依赖方向：`ui-primitives` 被所有业务包依赖，它自己不依赖任何业务包。
- 颜色只走令牌（`var(--token)` 或语义类），不写字面值 —— 令牌在 [`ui-theme`](../ui-theme/README.md)。

## 新增组件

```bash
npx shadcn@latest add <component-name>
```

`components.json` 的 `aliases.ui` 已指向本包，CLI 会直接把文件写进 `src/`。
新增后 `package.json` 的 `exports` 是通配 `./*`，无需登记。

## 用法

```tsx
import { Button } from "@v2/ui-primitives/button";
import { cn } from "@v2/ui-primitives/utils";
```

**业务代码禁止裸用原生标签**（`<button>` / `<input>` / `<textarea>`），统一走本包。
