import type { ComponentProps } from "react";

import { cn } from "@v2/ui-primitives/utils";

type MarkdownLinkProps = ComponentProps<"a">;

export function MarkdownLink({ className, href, children, ...props }: MarkdownLinkProps) {
  const external = href?.startsWith("http://") || href?.startsWith("https://");

  return (
    <a
      href={href}
      className={cn(
        "font-medium text-sky-600 underline decoration-sky-600/30 underline-offset-2 hover:decoration-sky-600/60",
        className,
      )}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      {...props}
    >
      {children}
    </a>
  );
}
