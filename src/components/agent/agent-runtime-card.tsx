import { useEffect, useState } from "react";
import { Download, ExternalLink, KeyRound, Loader2, LogIn, Star } from "lucide-react";
import type { AgentRuntimeItem } from "@/contracts/agent-runtime";
import { getAgentGuideUrl, supportsAgentLogin } from "@/lib/agent-runtime";
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
  downloading?: boolean;
  /** 0–100；有值时显示确定进度，否则下载中为不确定动画。 */
  downloadProgress?: number | null;
  downloadLabel?: string | null;
  onLogin?: () => void;
  onDownload?: () => void;
  onSetDefault?: () => void;
  onPreferredModelChange?: (modelId: string) => void;
}

/** 统一卡片的安装/鉴权阶段（由 catalog + probe 字段推导，不按 Agent 特判）。 */
type SetupPhase = "missing" | "probing" | "needs_auth" | "ready";

function resolveSetupPhase(agent: AgentRuntimeItem): SetupPhase {
  if (agent.status.state === "probing") return "probing";
  if (!agent.available) return "missing";
  if (agent.auth?.state === "authenticated" || agent.status.state === "ready") return "ready";
  if (
    agent.status.state === "auth_required" ||
    agent.auth?.state === "unauthenticated"
  ) {
    return "needs_auth";
  }
  return "ready";
}

function authBadgeClass(state: string | undefined): string {
  switch (state) {
    case "authenticated":
      return "bg-emerald-500/15 text-emerald-600";
    case "unauthenticated":
    case "unknown":
      return "bg-amber-500/15 text-amber-700";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function nextStepText(phase: SetupPhase, agent: AgentRuntimeItem): string | null {
  if (phase === "missing") {
    return agent.can_download
      ? "下一步：下载 CLI 到叮答托管目录"
      : "下一步：按文档安装 CLI，再点「扫描 Agent」";
  }
  if (phase === "needs_auth") {
    return supportsAgentLogin(agent) || agent.auth?.can_login
      ? "下一步：登录 CLI（或自行配置 API）"
      : "下一步：在终端登录或配置 API Key";
  }
  return null;
}

export function AgentRuntimeCard({
  agent,
  loggingIn = false,
  downloading = false,
  downloadProgress = null,
  downloadLabel = null,
  onLogin,
  onDownload,
  onSetDefault,
  onPreferredModelChange,
}: AgentRuntimeCardProps) {
  const { status } = agent;
  const guideUrl = getAgentGuideUrl(agent);
  const models = agent.models ?? [];
  const phase = resolveSetupPhase(agent);
  const probing = phase === "probing";
  const preferredInList =
    agent.preferred_model_id && models.some((model) => model.id === agent.preferred_model_id)
      ? agent.preferred_model_id
      : null;
  const [selectedModelId, setSelectedModelId] = useState(
    preferredInList ?? models[0]?.id ?? "",
  );

  useEffect(() => {
    if (models.length === 0) {
      setSelectedModelId("");
      return;
    }
    const next =
      agent.preferred_model_id && models.some((model) => model.id === agent.preferred_model_id)
        ? agent.preferred_model_id
        : models[0]!.id;
    setSelectedModelId(next);
  }, [agent.id, agent.preferred_model_id, agent.models]);

  const canLogin =
    phase === "needs_auth" &&
    (supportsAgentLogin(agent) || Boolean(agent.auth?.can_login)) &&
    Boolean(onLogin);
  const showConfigure =
    phase === "needs_auth" && !canLogin && Boolean(guideUrl);
  const showDownload = phase === "missing" && agent.can_download && Boolean(onDownload);
  const nextStep = nextStepText(phase, agent);
  const modelPlaceholder = probing ? "检测模型中…" : "暂无可用模型";
  const selectValue = models.length > 0 ? selectedModelId || models[0]?.id : null;

  return (
    <Card
      className={cn(
        "relative overflow-hidden transition hover:border-primary/40 hover:shadow-sm",
        phase === "missing" && "opacity-95",
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
              {agent.available && agent.version ? (
                <p className="text-[11px] text-muted-foreground">版本 {agent.version}</p>
              ) : null}
            </div>
          </div>
          <span className={cn("shrink-0 rounded-full px-1.5 py-0.5 text-[11px]", status.badge_class)}>
            {status.label}
          </span>
        </div>

        {nextStep ? (
          <p className="rounded-md bg-muted/50 px-2 py-1.5 text-xs text-muted-foreground">{nextStep}</p>
        ) : null}
        {agent.auth?.hint && phase === "needs_auth" ? (
          <p className="text-xs text-muted-foreground">{agent.auth.hint}</p>
        ) : null}
        {status.hint && phase === "missing" ? (
          <p className="text-xs text-muted-foreground">{status.hint}</p>
        ) : null}

        {agent.available ? (
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-muted-foreground">可用模型</span>
            <Select
              value={selectValue}
              onValueChange={(value) => {
                if (!value || value === selectedModelId) return;
                setSelectedModelId(value);
                onPreferredModelChange?.(value);
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

        {downloading ? (
          <div className="space-y-1.5 rounded-md border border-primary/20 bg-primary/5 px-2.5 py-2">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="inline-flex items-center gap-1.5 text-primary">
                <Loader2 className="size-3.5 animate-spin" />
                {downloadLabel ??
                  (downloadProgress != null ? `下载中 ${Math.round(downloadProgress)}%` : "下载中…")}
              </span>
              {downloadProgress != null ? (
                <span className="tabular-nums text-muted-foreground">
                  {Math.min(100, Math.max(0, Math.round(downloadProgress)))}%
                </span>
              ) : null}
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              {downloadProgress != null ? (
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                  style={{ width: `${Math.min(100, Math.max(0, downloadProgress))}%` }}
                />
              ) : (
                <div className="h-full w-1/3 animate-[download-indeterminate_1.2s_ease-in-out_infinite] rounded-full bg-primary will-change-transform" />
              )}
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          {showDownload ? (
            <Button
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={downloading}
              onClick={onDownload}
            >
              {downloading ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Download className="size-3" />
              )}
              {downloading ? "下载中…" : "下载 CLI"}
            </Button>
          ) : null}

          {canLogin ? (
            <Button size="sm" className="h-7 px-2 text-xs" disabled={loggingIn} onClick={onLogin}>
              <LogIn className="size-3" />
              {loggingIn ? "登录中…" : "登录"}
            </Button>
          ) : null}

          {showConfigure && guideUrl ? (
            <a
              href={guideUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({
                size: "sm",
                className: "h-7 px-2 text-xs",
              })}
            >
              <KeyRound className="size-3" />
              配置鉴权
            </a>
          ) : null}

          {phase === "missing" && guideUrl ? (
            <a
              href={guideUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({
                size: "sm",
                variant: "outline",
                className: "h-7 px-2 text-xs",
              })}
            >
              <ExternalLink className="size-3" />
              接入文档
            </a>
          ) : null}

          {agent.available && !agent.is_default ? (
            <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={onSetDefault}>
              设为默认
            </Button>
          ) : null}

          {phase === "needs_auth" && guideUrl && canLogin ? (
            <a
              href={guideUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({
                size: "sm",
                variant: "outline",
                className: "h-7 px-2 text-xs",
              })}
            >
              <ExternalLink className="size-3" />
              文档
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
