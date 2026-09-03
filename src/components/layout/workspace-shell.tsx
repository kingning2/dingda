import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface WorkspaceShellProps {
  children: ReactNode;
  className?: string;
}

/** 工作区主体容器。多 Tab 顶栏（WorkspaceTabsBar）留到打开项目页时再接入。 */
export function WorkspaceShell({ children, className }: WorkspaceShellProps) {
  return <div className={cn("h-full w-full overflow-hidden", className)}>{children}</div>;
}
