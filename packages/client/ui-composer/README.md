# packages/client/ui-composer

输入区：Prompt 编辑器、附件、Agent 选择。

包名 `@v2/ui-composer`。

## 文件

- `src/attachment-utils.ts`
- `src/composer-agent-picker.tsx`
- `src/composer-agents.ts`
- `src/composer-attachments.tsx`
- `src/index.ts`
- `src/prompt-composer.tsx`

## 依赖

- 工作区：@v2/contracts / @v2/ui-agent / @v2/ui-crawler / @v2/ui-primitives
- 外部：lucide-react
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
