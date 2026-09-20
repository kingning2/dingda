/**
 * 扫码登录块：居中二维码卡，不用浏览器直播页卡样式。
 *
 * 职责：
 *   渲染 AI 聊天里的登录步骤（kind=login）：标题 + 状态 + 二维码，提示用户用 App 扫码。
 *
 * 设计说明：
 *   - 与 step 块的 PagePreview（地址栏 / LIVE / 网页截图）刻意区分 —— 登录不是在「看网页」。
 *   - 二维码来自 step.page.screenshot_url（后端仍走 browserFrame 推图，只是 UI 换壳）。
 *   - 文件末尾自注册，Chat 通过注册表取用。
 */

import { Loader2, QrCode } from "lucide-react";
import { Badge } from "@v2/ui-primitives/badge";
import { cn } from "@v2/ui-primitives/utils";
import { Collapse } from "./collapse";
import { CodexActivityIndicator } from "./thinking-orb";
import { registerBlock } from "../chat/registry";
import type { ChatBlockProps } from "../chat/types";

function isRunning(state: string): boolean {
  return state === "running" || state === "browsing" || state === "pending";
}

/** 扫码登录块：折叠标题 + 居中二维码卡。 */
export function LoginBlock({ block }: ChatBlockProps<"login">) {
  const { step } = block;
  const running = isRunning(step.status.state);
  const page = step.page;
  const qrUrl = page?.screenshot_url ?? null;
  const hint = page?.focus_label || step.hint || "用 App 扫码登录";

  const title = (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      {running ? (
        <CodexActivityIndicator className="w-3.5 shrink-0 text-[13px] text-sky-600" />
      ) : (
        <QrCode className="size-3.5 shrink-0 text-muted-foreground/70" />
      )}
      <span className="min-w-0 truncate">
        <span className="font-medium text-foreground/90">{step.label}</span>
        {hint ? <span className="text-muted-foreground"> · {hint}</span> : null}
      </span>
    </span>
  );

  const trailing = (
    <span
      className={
        step.status.state === "error"
          ? "shrink-0 text-[11px] text-destructive"
          : "shrink-0 text-[11px] text-muted-foreground"
      }
    >
      {step.status.label}
    </span>
  );

  return (
    <Collapse
      testId="login-block"
      title={title}
      trailing={trailing}
      defaultOpen
      lifecycleOpen={running ? true : undefined}
    >
      <div className="flex flex-col items-center gap-3 rounded-md border border-border/70 bg-background px-4 py-5">
        {qrUrl ? (
          <div className="flex size-48 items-center justify-center overflow-hidden rounded-xl border border-border bg-white p-3">
            <img
              src={qrUrl}
              alt="登录二维码"
              className="size-full object-contain"
              decoding="async"
            />
          </div>
        ) : (
          <div className="flex size-48 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-muted-foreground">
            {running ? (
              <Loader2 className="size-7 animate-spin" />
            ) : (
              <QrCode className="size-7 opacity-50" />
            )}
            <span className="text-[11px]">{running ? "正在生成二维码…" : "暂无二维码"}</span>
          </div>
        )}
        <p
          className={cn(
            "text-center text-sm",
            step.status.state === "error"
              ? "text-destructive"
              : step.status.state === "ready"
                ? "text-emerald-600"
                : "text-muted-foreground",
          )}
        >
          {hint}
        </p>
        {running ? (
          <Badge variant="secondary" className="gap-1.5">
            <Loader2 className="size-3 animate-spin" />
            等待扫码…
          </Badge>
        ) : null}
      </div>
    </Collapse>
  );
}

registerBlock("login", LoginBlock);
