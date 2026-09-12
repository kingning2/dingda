import { Check, Plug } from "lucide-react";
import type { ComposerAgentOption } from "@v2/contracts/composer";
import { AgentIcon } from "@/components/agent/agent-icon";
import { buttonVariants } from "@v2/ui-primitives/button";
import { cn } from "@v2/ui-primitives/utils";

interface SettingsProps {
  agents: ComposerAgentOption[];
  agentId: string | null;
  modelId: string | null;
  disabled?: boolean;
  onChange: (agentId: string, modelId: string | null) => void;
}

/** 右侧设置：选择 Agent / 模型。 */
export function Settings({
  agents,
  agentId,
  modelId,
  disabled = false,
  onChange,
}: SettingsProps) {
  const selectedAgent = agents.find((agent) => agent.id === agentId) ?? agents[0] ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="shrink-0 border-b border-border/70 px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">设置</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">选择本轮对话使用的 Agent 与模型</p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {agents.length === 0 ? (
          <a
            href="#/agents"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5")}
          >
            <Plug className="size-3.5" />
            管理 Agent
          </a>
        ) : (
          <div className="space-y-4">
            <section className="space-y-2">
              <h3 className="text-xs font-medium text-muted-foreground">Agent</h3>
              <div className="space-y-1">
                {agents.map((agent) => {
                  const selected = agent.id === selectedAgent?.id;
                  return (
                    <button
                      key={agent.id}
                      type="button"
                      disabled={disabled}
                      onClick={() => {
                        const firstModel = agent.models?.[0]?.id ?? null;
                        onChange(agent.id, firstModel);
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                        selected
                          ? "border-foreground/20 bg-secondary"
                          : "border-transparent hover:bg-muted/50",
                        disabled && "opacity-60",
                      )}
                    >
                      <AgentIcon id={agent.id} size={20} />
                      <span className="min-w-0 flex-1 truncate">{agent.name}</span>
                      {agent.is_default ? (
                        <span className="text-[10px] text-muted-foreground">默认</span>
                      ) : null}
                      {selected ? <Check className="size-3.5 shrink-0" /> : null}
                    </button>
                  );
                })}
              </div>
            </section>

            {selectedAgent?.models && selectedAgent.models.length > 0 ? (
              <section className="space-y-2">
                <h3 className="text-xs font-medium text-muted-foreground">模型</h3>
                <div className="space-y-1">
                  {selectedAgent.models.map((model) => {
                    const selected = model.id === modelId;
                    return (
                      <button
                        key={model.id}
                        type="button"
                        disabled={disabled}
                        onClick={() => onChange(selectedAgent.id, model.id)}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                          selected
                            ? "border-foreground/20 bg-secondary"
                            : "border-transparent hover:bg-muted/50",
                          disabled && "opacity-60",
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">{model.label}</span>
                        {selected ? <Check className="size-3.5 shrink-0" /> : null}
                      </button>
                    );
                  })}
                </div>
              </section>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
