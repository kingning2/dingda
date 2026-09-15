# markdown/

Markdown 渲染：助手消息里 Markdown 正文到 React 的映射。

## 文件

- `MarkdownRenderer.tsx` — 入口：封装 `react-markdown` + `remark-gfm`，注册自定义组件。
- `CodeBlock.tsx` — 代码块（内联 / fenced）。
- `Link.tsx` — 链接（外部自动新标签）。
- `Table.tsx` — 表格（含表头、行、单元格）。
- `index.ts` — barrel，统一导出。

## 消费方

`blocks/text.tsx`（助手正文块）、`blocks/step.tsx`（步骤详情）。

不直接暴露给包外；包外取 `MarkdownRenderer` 走包入口 `index.ts`。
