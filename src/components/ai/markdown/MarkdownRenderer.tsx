import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

import { cn } from "@/lib/utils";
import { MarkdownCode } from "./CodeBlock";
import { MarkdownLink } from "./Link";
import {
  MarkdownTable,
  MarkdownTableCell,
  MarkdownTableHead,
  MarkdownTableHeaderCell,
  MarkdownTableRow,
} from "./Table";

const markdownComponents: Components = {
  a: ({ node: _node, ...props }) => <MarkdownLink {...props} />,
  code: ({ node: _node, className, children, ...props }) => {
    const isBlock = /language-/.test(className ?? "");
    return (
      <MarkdownCode className={className} inline={!isBlock} {...props}>
        {children}
      </MarkdownCode>
    );
  },
  pre: ({ node: _node, children }) => <>{children}</>,
  table: ({ node: _node, ...props }) => <MarkdownTable {...props} />,
  thead: ({ node: _node, ...props }) => <MarkdownTableHead {...props} />,
  tr: ({ node: _node, ...props }) => <MarkdownTableRow {...props} />,
  th: ({ node: _node, ...props }) => <MarkdownTableHeaderCell {...props} />,
  td: ({ node: _node, ...props }) => <MarkdownTableCell {...props} />,
  p: ({ node: _node, ...props }) => (
    <p className="mb-2 last:mb-0 break-words leading-relaxed" {...props} />
  ),
  ul: ({ node: _node, ...props }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0" {...props} />,
  ol: ({ node: _node, ...props }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0" {...props} />,
  li: ({ node: _node, ...props }) => <li className="leading-relaxed" {...props} />,
  blockquote: ({ node: _node, ...props }) => (
    <blockquote
      className="my-2 border-l-2 border-border pl-3 text-muted-foreground italic"
      {...props}
    />
  ),
  h1: ({ node: _node, ...props }) => <h1 className="mb-2 text-lg font-semibold" {...props} />,
  h2: ({ node: _node, ...props }) => <h2 className="mb-2 text-base font-semibold" {...props} />,
  h3: ({ node: _node, ...props }) => <h3 className="mb-1.5 text-sm font-semibold" {...props} />,
  hr: ({ node: _node, ...props }) => <hr className="my-3 border-border/80" {...props} />,
};

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  if (!content.trim()) return null;

  return (
    <div
      className={cn(
        "min-w-0 overflow-x-auto break-words text-sm text-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
