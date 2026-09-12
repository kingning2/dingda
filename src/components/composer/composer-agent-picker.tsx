import { Check, ChevronDown, Plug } from "lucide-react";
import type { ComposerAgentOption } from "@v2/contracts/composer";
import { AgentIcon } from "@/components/agent/agent-icon";
import { buttonVariants } from "@v2/ui-primitives/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@v2/ui-primitives/dropdown-menu";
import { cn } from "@v2/ui-primitives/utils";

interface ComposerAgentPickerProps {
  agents: ComposerAgentOption[];
  agentId: string | null;
  modelId: string | null;
  onChange: (agentId: string, modelId: string | null) => void;
  disabled?: boolean;
  className?: string;
}

export function ComposerAgentPicker({
  agents,
  agentId,
  modelId,
  onChange,
  disabled = false,
  className,
}: ComposerAgentPickerProps) {
  const selectedAgent = agents.find((agent) => agent.id === agentId) ?? agents[0] ?? null;
  const selectedModel = selectedAgent?.models?.find((model) => model.id === modelId) ?? null;

  if (agents.length === 0) {
    return (
      <a
        href="#/agents"
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "gap-1.5 text-muted-foreground",
          className,
        )}
      >
        <Plug className="size-3.5" />
        管理 Agent
      </a>
    );
  }

  const triggerLabel = selectedAgent
    ? selectedModel
      ? `${selectedAgent.name} · ${selectedModel.label}`
      : selectedAgent.name
    : "选择 Agent";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "max-w-[220px] gap-1.5 px-2 font-normal",
          className,
        )}
      >
        {selectedAgent ? (
          <>
            <AgentIcon id={selectedAgent.id} size={18} />
            <span className="truncate">{triggerLabel}</span>
          </>
        ) : (
          <span>选择 Agent</span>
        )}
        <ChevronDown className="size-3.5 shrink-0 opacity-60" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-56 overflow-y-auto">
        {agents.map((agent) => {
          const isAgentSelected = agent.id === selectedAgent?.id;
          const models = agent.models ?? [];

          if (models.length === 0) {
            return (
              <DropdownMenuItem
                key={agent.id}
                onClick={() => onChange(agent.id, null)}
                className="gap-2"
              >
                <AgentIcon id={agent.id} size={20} />
                <span className="truncate">{agent.name}</span>
                {agent.is_default ? (
                  <span className="ml-auto text-[10px] text-muted-foreground">默认</span>
                ) : null}
                {isAgentSelected ? <Check className="ml-auto size-3.5" /> : null}
              </DropdownMenuItem>
            );
          }

          return (
            <DropdownMenuSub key={agent.id}>
              <DropdownMenuSubTrigger className="gap-2">
                <AgentIcon id={agent.id} size={20} />
                <span className="truncate">{agent.name}</span>
                {agent.is_default ? (
                  <span className="text-[10px] text-muted-foreground">默认</span>
                ) : null}
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="max-h-72 w-56 overflow-y-auto">
                {models.map((model) => {
                  const isModelSelected = isAgentSelected && model.id === modelId;
                  return (
                    <DropdownMenuItem
                      key={`${agent.id}:${model.id}`}
                      onClick={() => onChange(agent.id, model.id)}
                      className="gap-2"
                    >
                      <span className="truncate">{model.label}</span>
                      {isModelSelected ? <Check className="ml-auto size-3.5" /> : null}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
