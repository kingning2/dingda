# packages/client/ui-ai

AI 消息渲染：消息块、Markdown、思考过程。

包名 `@v2/ui-ai`。

## 文件

- `src/Collapse.tsx`
- `src/ComparisonResults.tsx`
- `src/ProductPreviewHost.tsx`
- `src/Products.tsx`
- `src/README.md`
- `src/Settings.tsx`
- `src/ThinkingOrb.tsx`
- `src/XianyuPreviewDialog.tsx`
- `src/XiaohongshuPreviewDialog.tsx`
- `src/blocks\index.ts`
- `src/blocks\step.tsx`
- `src/blocks\text.tsx`
- `src/blocks\thinking.tsx`
- `src/blocks\user.tsx`
- `src/index.ts`
- `src/layout.tsx`
- `src/markdown\CodeBlock.tsx`
- `src/markdown\Link.tsx`
- `src/markdown\MarkdownRenderer.tsx`
- `src/markdown\Table.tsx`
- `src/markdown\index.ts`
- `src/mockData.ts`
- `src/scheduler.tsx`
- `src/session.ts`
- `src/stick-to-bottom.ts`
- `src/useRevealText.ts`

## 依赖

- 工作区：@v2/contracts / @v2/runtime / @v2/ui-agent / @v2/ui-composer / @v2/ui-crawler / @v2/ui-primitives
- 外部：@tanstack/react-virtual / lucide-react / react-markdown / remark-gfm
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
