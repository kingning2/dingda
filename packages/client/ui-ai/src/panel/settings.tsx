/**
 * 右侧设置面板：展示当前 Agent。
 *
 * 外部 CLI Agent 已移除，产品只剩内置 dingda；模型由 Server 侧
 * `DINGDA_LLM_*` 环境变量决定，这里只读展示、不再提供选择。
 */

import { cn } from "@v2/ui-primitives/utils";

interface SettingsProps {
  disabled?: boolean;
}

/** 右侧设置：当前 Agent 信息。 */
export function Settings({ disabled = false }: SettingsProps) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="shrink-0 border-b border-border/70 px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">设置</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">当前对话使用的 Agent</p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <section className="space-y-2">
          <h3 className="text-xs font-medium text-muted-foreground">Agent</h3>
          <div
            className={cn(
              "flex items-center gap-2 rounded-md border px-3 py-2 text-sm",
              disabled && "opacity-60",
            )}
          >
            <span className="flex size-5 shrink-0 items-center justify-center rounded bg-primary/10 text-[11px] font-semibold">
              叮
            </span>
            <span className="min-w-0 flex-1 truncate">叮答（内置）</span>
            <span className="text-[10px] text-muted-foreground">默认</span>
          </div>
          <p className="text-xs text-muted-foreground">
            模型由服务器配置（DINGDA_LLM_*）决定，无需在客户端选择。
          </p>
        </section>
      </div>
    </div>
  );
}
