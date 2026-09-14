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
import type { ComposerAgentOption, ComposerSubmitPayload } from "@v2/contracts/composer";
import { PromptComposer } from "@v2/ui-composer";

export interface ComposerFooterProps {
  agents: ComposerAgentOption[];
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

export const ComposerFooter = memo(function ComposerFooter({
  agents,
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
