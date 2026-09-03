import { useEffect, useState } from "react";
import { ExternalLink, LogIn, Star } from "lucide-react";
import type { AgentRuntimeItem } from "@/contracts/agent-runtime";
import { getAgentGuideUrl } from "@/lib/agent-runtime";
import { AgentIcon } from "@/components/agent/agent-icon";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface AgentRuntimeCardProps {
  agent: AgentRuntimeItem;
  loggingIn?: boolean;
  onLogin?: () => void;
  onSetDefault?: () => void;
}

function authBadgeClass(state: string | undefined): string {
  switch (state) {
    case "authenticated":
      return "bg-emerald-500/15 text-emerald-600";
    case "unauthenticated":
      return "bg-amber-500/15 text-amber-700";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function AgentRuntimeCard({
  agent,
  loggingIn = false,
  onLogin,
  onSetDefault,
}: AgentRuntimeCardProps) {
  const { status } = agent;
  const guideUrl = getAgentGuideUrl(agent);
  const models = agent.models ?? [];
  const probing = status.state === "probing";
  const [selectedModelId, setSelectedModelId] = useState(models[0]?.id ?? "");

  useEffect(() => {
    if (models.length > 0) {
      setSelectedModelId(models[0].id);
    }
  }, [agent.id, models]);

  const showLogin =
    agent.available && agent.auth?.can_login && agent.auth.state !== "authenticated" && onLogin;

  const showStatusHint =
    status.hint && status.state !== "ready" && status.state !== "missing";

  const modelPlaceholder = probing ? "检测模型中…" : "暂无可用模型";
  const selectValue = models.length > 0 ? selectedModelId || models[0]?.id : null;

  return (
    <Card
      className={cn(
        "relative overflow-hidden transition hover:border-primary/40 hover:shadow-sm",
        !agent.available && "opacity-95",
      )}
    >
      <CardContent className="flex flex-col gap-2.5 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 gap-2.5">
            <AgentIcon id={agent.id} size={28} className="mt-0.5 shrink-0" />
            <div className="min-w-0 space-y-0.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="text-sm font-medium leading-tight">{agent.name}</p>
                {agent.is_default ? (
                  <span className="inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">
                    <Star className="size-2.5" />
                    默认
                  </span>
                ) : null}
                {agent.auth ? (
                  <Badge
                    className={cn(
                      "h-auto rounded-full border-transparent px-1.5 py-0 text-[10px]",
                      authBadgeClass(agent.auth.state),
                    )}
                  >
                    {agent.auth.label}
                  </Badge>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">{agent.description}</p>
              {agent.available && agent.command ? (
                <p className="truncate font-mono text-[11px] text-muted-foreground">{agent.command}</p>
              ) : null}
              {agent.available && agent.version ? (
                <p className="text-[11px] text-muted-foreground">版本 {agent.version}</p>
              ) : null}
              {!agent.available && guideUrl ? (
                <a
                  href={guideUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <ExternalLink className="size-3" />
                  查看接入文档
                </a>
              ) : null}
            </div>
          </div>
          <span className={cn("shrink-0 rounded-full px-1.5 py-0.5 text-[11px]", status.badge_class)}>
            {status.label}
          </span>
        </div>

        {showStatusHint ? <p className="text-xs text-muted-foreground">{status.hint}</p> : null}
        {agent.auth?.hint ? <p className="text-xs text-muted-foreground">{agent.auth.hint}</p> : null}

        {agent.available ? (
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-muted-foreground">可用模型</span>
            <Select
              value={selectValue}
              onValueChange={(value) => {
                if (value) setSelectedModelId(value);
              }}
              disabled={probing || models.length === 0}
            >
              <SelectTrigger size="sm" className="w-full">
                <SelectValue placeholder={modelPlaceholder} />
              </SelectTrigger>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          {agent.available ? (
            <>
              {showLogin ? (
                <Button size="sm" className="h-7 px-2 text-xs" disabled={loggingIn} onClick={onLogin}>
                  <LogIn className="size-3" />
                  {loggingIn ? "登录中…" : "登录"}
                </Button>
              ) : null}
              {!agent.is_default ? (
                <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={onSetDefault}>
                  设为默认
                </Button>
              ) : null}
            </>
          ) : guideUrl ? (
            <a
              href={guideUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ size: "sm", variant: "outline", className: "h-7 px-2 text-xs" })}
            >
              <ExternalLink className="size-3" />
              接入文档
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
