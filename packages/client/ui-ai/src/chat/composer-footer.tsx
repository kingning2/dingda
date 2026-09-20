/**
 * 聊天输入框。
 *
 * 职责：
 *   渲染底部输入区：可选的运行状态行 + PromptComposer。
 *
 * 设计说明：
 *   - 只是 PromptComposer 的定位与默认值包装，**不持有任何状态** ——
 *     Agent 列表、占位文案、可用性全部由上层传入。
 *   - memo 是因为它挂在聊天面板底部：记录区每次流式更新都会重渲染父组件，
 *     而本组件的入参在流式期间基本不变。
 *   - 用 `memo` 而不是 `useMemo`：这里要挡住的是父组件重渲染，不是值的重算。
 */

import { memo, type ReactNode } from "react";
import type { LlmCredentialItem } from "@v2/contracts/model";
import type { ComposerAgentOption, ComposerSubmitPayload } from "@v2/contracts/composer";
import { PromptComposer } from "@v2/ui-composer";
import { ProviderIcon } from "@v2/ui-model-config/provider-icon";

/** ComposerFooter 的 props。 */
export interface ComposerFooterProps {
  agents: ComposerAgentOption[];
  /** 本地服务是否就绪；就绪后才展示当前模型。 */
  serverReady?: boolean;
  /** 服务端下一次调用会使用的使用中凭据。 */
  activeCredential?: LlmCredentialItem | null;
  defaultAgentId?: string | null;
  defaultModelId?: string | null;
  placeholder?: string | null;
  disabled: boolean;
  busy: boolean;
  /** 输入框上方的运行状态行；没有活动回合时传 null。 */
  status?: ReactNode;
  onSend?: (payload: ComposerSubmitPayload) => void;
  onCancel?: () => void;
  onInputActivity?: () => void;
}

/** 输入框底部栏：发送按钮、取消按钮、字数提示。 */
export const ComposerFooter = memo(function ComposerFooter({
  agents,
  serverReady = false,
  activeCredential = null,
  defaultAgentId,
  defaultModelId,
  placeholder,
  disabled,
  busy,
  status,
  onSend,
  onCancel,
  onInputActivity,
}: ComposerFooterProps) {
  return (
    <footer className="shrink-0 border-t border-border/60 bg-background px-4 py-3">
      {serverReady ? (
        <div className="mx-auto mb-2 w-full max-w-3xl">
          <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-border/60 bg-card/70 px-2.5 py-1 text-xs text-muted-foreground">
            {activeCredential ? (
              <>
                <ProviderIcon id={activeCredential.provider} className="size-4" />
                <span className="truncate">
                  {activeCredential.label ? `${activeCredential.label} · ` : ""}
                  <span className="font-medium text-foreground">{activeCredential.provider_name}</span>
                  {" · "}
                  <span className="font-mono">{activeCredential.model}</span>
                </span>
              </>
            ) : (
              "当前模型：跟随服务端配置"
            )}
          </div>
        </div>
      ) : null}
      {status ? <div className="mx-auto w-full max-w-3xl">{status}</div> : null}
      <div className="mx-auto w-full max-w-3xl">
        <PromptComposer
          agents={agents}
          defaultAgentId={defaultAgentId}
          defaultModelId={defaultModelId}
          hideAgentPicker
          showPromptGlyph
          placeholder={placeholder ?? "Ask Codex to do anything"}
          disabled={disabled}
          busy={busy}
          minRows={3}
          textareaClassName="min-h-[72px] text-sm"
          onSubmit={(payload) => onSend?.(payload)}
          onCancel={onCancel}
          onInputActivity={onInputActivity}
        />
      </div>
    </footer>
  );
});
