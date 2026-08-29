/**
 * 统一错误码组件 — 只覆盖右侧内容区，不全屏接管窗口。
 */

import type { ReactNode } from "react";

/**
 * `ErrorPage` 属性。
 */
export interface ErrorPageProps {
  /** 错误状态码，如 "503"。 */
  code: string;
  /** 错误标题。 */
  title: string;
  /** 错误描述；缺省时不渲染。 */
  description?: string;
  /** 底部操作区（如重试按钮）；缺省时不渲染。 */
  action?: ReactNode;
}

/**
 * 错误态容器：填充父级内容区，保持标题栏与侧栏可见。
 */
export function ErrorPage({ code, title, description, action }: ErrorPageProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6">
      <div className="flex max-w-md flex-col items-center gap-2 text-center">
        <h1 className="text-[7rem] font-bold leading-tight tracking-tight">{code}</h1>
        <p className="text-[length:var(--text-lg)] font-medium text-foreground">{title}</p>
        {description ? (
          <p className="text-[length:var(--text-sm)] text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
