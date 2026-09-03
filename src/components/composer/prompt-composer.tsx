import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import type { ComposerAgentOption, ComposerAttachmentView, ComposerSubmitPayload } from "@/contracts/composer";
import { ComposerAgentPicker } from "./composer-agent-picker";
import { ComposerAttachments } from "./composer-attachments";
import {
  filesToComposerAttachments,
  revokeComposerAttachmentUrl,
  revokeComposerAttachmentUrls,
} from "./attachment-utils";
import { resolveComposerSelection } from "./composer-agents";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface PromptComposerProps {
  agents: ComposerAgentOption[];
  placeholder?: string;
  disabled?: boolean;
  busy?: boolean;
  defaultAgentId?: string | null;
  defaultModelId?: string | null;
  defaultMessage?: string;
  onSubmit: (payload: ComposerSubmitPayload) => void;
  className?: string;
  textareaClassName?: string;
  minRows?: number;
}

export function PromptComposer({
  agents,
  placeholder = "描述你想创建的内容…",
  disabled = false,
  busy = false,
  defaultAgentId = null,
  defaultModelId = null,
  defaultMessage = "",
  onSubmit,
  className,
  textareaClassName,
  minRows = 4,
}: PromptComposerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState(defaultMessage);
  const [attachments, setAttachments] = useState<ComposerAttachmentView[]>([]);
  const [agentId, setAgentId] = useState<string | null>(defaultAgentId);
  const [modelId, setModelId] = useState<string | null>(defaultModelId);

  const { agentId: resolvedAgentId, modelId: resolvedModelId } = useMemo(
    () => resolveComposerSelection(agents, agentId, modelId),
    [agentId, agents, modelId],
  );

  useEffect(() => {
    return () => {
      revokeComposerAttachmentUrls(attachments);
    };
  }, [attachments]);

  useEffect(() => {
    setMessage(defaultMessage);
  }, [defaultMessage]);

  useEffect(() => {
    if (defaultAgentId) {
      setAgentId(defaultAgentId);
    }
  }, [defaultAgentId]);

  useEffect(() => {
    if (defaultModelId) {
      setModelId(defaultModelId);
    }
  }, [defaultModelId]);

  const canSubmit =
    !disabled &&
    !busy &&
    Boolean(resolvedAgentId) &&
    (message.trim().length > 0 || attachments.length > 0);

  async function appendFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (list.length === 0) return;
    const next = await filesToComposerAttachments(list, attachments.length);
    if (next.length === 0) return;
    setAttachments((current) => [...current, ...next]);
  }

  function handleRemoveAttachment(id: string) {
    setAttachments((current) => {
      const target = current.find((item) => item.id === id);
      if (target) revokeComposerAttachmentUrl(target);
      return current.filter((item) => item.id !== id);
    });
  }

  function handleSubmit() {
    if (!canSubmit || !resolvedAgentId) return;
    const trimmed = message.trim();
    onSubmit({
      message: trimmed,
      agent_id: resolvedAgentId,
      model_id: resolvedModelId,
      attachments: attachments.map((item) => ({ ...item })),
    });
    setMessage("");
    revokeComposerAttachmentUrls(attachments);
    setAttachments([]);
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <ComposerAttachments items={attachments} onRemove={handleRemoveAttachment} className="px-1" />

      <Textarea
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleSubmit();
          }
        }}
        onPaste={(event) => {
          const files = event.clipboardData?.files;
          if (!files || files.length === 0) return;
          event.preventDefault();
          void appendFiles(files);
        }}
        placeholder={placeholder}
        rows={minRows}
        disabled={disabled || busy}
        className={cn(
          "min-h-[120px] resize-none border-0 bg-transparent px-1 py-1 text-[15px] leading-relaxed shadow-none focus-visible:ring-0",
          textareaClassName,
        )}
      />

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,.pdf,.txt,.md,.csv,.json"
        multiple
        className="hidden"
        onChange={(event) => {
          const files = event.target.files;
          if (files) void appendFiles(files);
          event.target.value = "";
        }}
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <ComposerAgentPicker
            agents={agents}
            agentId={resolvedAgentId}
            modelId={resolvedModelId}
            onChange={(nextAgentId, nextModelId) => {
              setAgentId(nextAgentId);
              setModelId(nextModelId);
            }}
            disabled={disabled || busy}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            disabled={disabled || busy}
            aria-label="上传图片或附件"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip className="size-4" />
          </Button>
        </div>
        <Button
          type="button"
          size="icon"
          className="rounded-full"
          disabled={!canSubmit}
          onClick={handleSubmit}
          aria-label="发送"
        >
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </div>
  );
}
