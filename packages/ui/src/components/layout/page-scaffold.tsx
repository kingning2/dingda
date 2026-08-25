/**
 * 工作区页面基础容器 — 占满右侧 MainPanel，支持 ProComponents 式头/工具栏/底栏与滚动策略。
 *
 * Feature 页应包在本组件内，不要在页面里写 `overflow-auto`。
 * 分栏页若自行管理内部滚动，传 `scroll={false}`。
 *
 * @author Xiaoman
 * @created 2026-07-20
 */

import * as React from "react";

import { cn } from "../../lib/cn";
import { AmbientSpotlight } from "../effects/ambient-spotlight";
import { ScrollArea } from "../scroll-area";
import { useReducedMotion } from "../../motion";
import { PageContainer } from "./page-container";
import { PageHeader } from "./page-header";

/** 页头 / 工具栏随内容滚动，或固定在工作区顶部。 */
export type PageHeaderMode = "fixed" | "scroll";

/**
 * 工作区页面容器属性。
 *
 * @author Xiaoman
 * @created 2026-07-20
 */
export interface PageScaffoldProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  /** 页头主标题；与 {@link PageHeader} 联动。 */
  title?: React.ReactNode;
  /**
   * 页面说明。
   * - 有 {@link title} 时：作为页头副标题；
   * - 无 title 时：渲染在滚动内容顶部（旧用法兼容）。
   */
  subtitle?: React.ReactNode;
  /** 页头右侧操作区。 */
  extra?: React.ReactNode;
  /** 工具栏（筛选、搜索等）；通常与 `headerMode="fixed"` 搭配。 */
  toolbar?: React.ReactNode;
  /** 自定义页头；提供时替代内置 {@link PageHeader}。 */
  header?: React.ReactNode;
  /** 固定底栏（分页、批量操作等）。 */
  footer?: React.ReactNode;
  /**
   * 页头与工具栏滚动策略。
   * - `fixed`：固定于滚动区外；
   * - `scroll`：随内容一起滚动。
   *
   * 默认：存在 title / toolbar / header 时为 `fixed`，否则为 `scroll`。
   */
  headerMode?: PageHeaderMode;
  /** 页面主体。 */
  children?: React.ReactNode;
  /** 内容区最大宽度。 */
  containerWidth?: "full" | "lg" | "xl";
  /** 内容区内边距。 */
  containerPadding?: "none" | "sm" | "md" | "lg";
  /**
   * 占满主面板（flex 列）。
   *
   * @default true
   */
  fill?: boolean;
  /**
   * 内容超出时用 ScrollArea 滚动。
   * 分栏自管滚动时设为 `false`。
   *
   * @default true
   */
  scroll?: boolean;
  /** 环境背景。默认 `spotlight`；不需要光效时传 `none`。 */
  ambient?: "spotlight" | "none";
}

/**
 * 渲染内置或自定义页头 + 工具栏块。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
function PageChromeBlock({
  header,
  title,
  subtitle,
  extra,
  toolbar,
}: Pick<PageScaffoldProps, "header" | "title" | "subtitle" | "extra" | "toolbar">) {
  const hasBuiltInHeader = Boolean(title || extra || (subtitle && title));
  const headerSubtitle = title ? subtitle : undefined;

  if (!header && !hasBuiltInHeader && !toolbar) {
    return null;
  }

  return (
    <div className="space-y-4">
      {header ?? (
        <PageHeader title={title} subtitle={headerSubtitle} extra={extra} />
      )}
      {toolbar ? <div>{toolbar}</div> : null}
    </div>
  );
}

/**
 * 工作区页面基础容器。
 *
 * 负责：
 * - 占满右侧工作区画布
 * - ProComponents 式 fixed / scroll 页头
 * - 固定底栏 + 中间 ScrollArea
 * - 统一内边距与内容宽度
 *
 * @author Xiaoman
 * @created 2026-07-20
 *
 * @param props - 见 {@link PageScaffoldProps}
 * @returns 页面容器节点
 */
export function PageScaffold({
  title,
  subtitle,
  extra,
  toolbar,
  header,
  footer,
  headerMode: headerModeProp,
  children,
  containerWidth = "full",
  containerPadding = "md",
  fill = true,
  scroll = true,
  ambient = "spotlight",
  className,
  ...props
}: PageScaffoldProps) {
  const reducedMotion = useReducedMotion();
  const hasChrome = Boolean(header || title || extra || toolbar);
  const headerMode =
    headerModeProp ?? (hasChrome ? ("fixed" satisfies PageHeaderMode) : ("scroll" satisfies PageHeaderMode));
  const legacySubtitle = !title && subtitle ? subtitle : null;
  const chrome = (
    <PageChromeBlock
      header={header}
      title={title}
      subtitle={subtitle}
      extra={extra}
      toolbar={toolbar}
    />
  );

  const scrollBody = (
    <PageContainer
      width={containerWidth}
      padding={containerPadding}
      className={cn(
        "space-y-4",
        headerMode === "fixed" && hasChrome && "pt-4",
        !scroll && "flex h-full min-h-0 flex-1 flex-col",
        className,
      )}
      {...props}
    >
      {headerMode === "scroll" ? chrome : null}
      {legacySubtitle ? (
        <p className="text-[length:var(--text-sm)] text-muted-foreground">{legacySubtitle}</p>
      ) : null}
      {children}
    </PageContainer>
  );

  return (
    <div className={cn("relative flex min-h-0 flex-col overflow-hidden", fill && "flex-1")}>
      {ambient === "spotlight" && !reducedMotion ? <AmbientSpotlight /> : null}
      {headerMode === "fixed" && hasChrome ? (
        <PageContainer
          width={containerWidth}
          padding={containerPadding}
          className="shrink-0 space-y-4 border-b border-border/60 pb-4"
        >
          {chrome}
        </PageContainer>
      ) : null}

      {scroll ? (
        <ScrollArea className="min-h-0 flex-1">{scrollBody}</ScrollArea>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{scrollBody}</div>
      )}

      {footer ? (
        <PageContainer
          width={containerWidth}
          padding={containerPadding}
          className="shrink-0 border-t border-border/60 pt-4"
        >
          {footer}
        </PageContainer>
      ) : null}
    </div>
  );
}
