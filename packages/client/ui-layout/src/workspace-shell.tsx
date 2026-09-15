import type { ReactNode } from "react";
import { cn } from "@v2/ui-primitives/utils";

interface WorkspaceShellProps {
  children: ReactNode;
  className?: string;
}

/** 工作区主体容器（纯布局）。 */
export function WorkspaceShell({ children, className }: WorkspaceShellProps) {
  return <div className={cn("h-full w-full overflow-hidden", className)}>{children}</div>;
}
