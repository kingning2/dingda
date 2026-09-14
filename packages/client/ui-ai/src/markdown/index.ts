/**
 * Markdown 渲染组件 barrel。
 *
 * 职责：把 ui-primitives 里没有的 Markdown 元素（代码块、链接、表格）
 * 统一从这里取，不分散在各消费方里各自 import。
 */
export { MarkdownRenderer } from "./MarkdownRenderer";
export { MarkdownCode } from "./CodeBlock";
export { MarkdownLink } from "./Link";
export {
  MarkdownTable,
  MarkdownTableCell,
  MarkdownTableHead,
  MarkdownTableHeaderCell,
  MarkdownTableRow,
} from "./Table";
