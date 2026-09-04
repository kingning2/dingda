import { ExternalLink } from "lucide-react";

import type { AgentWorkProductItem, AgentWorkStepView } from "@/contracts/ai-work";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WorkStatusBadge } from "@/components/ai-work/work-status-badge";
import { isAgentRunningState } from "@/components/ai-work/agent-motion";
import { ProductCardStrip, toProductCardItem } from "../product/ProductCard";
import { cn } from "@/lib/utils";

interface ToolCallCardProps {
  step: AgentWorkStepView;
  selected?: boolean;
  pageUrl?: string | null;
  products?: AgentWorkProductItem[];
  onSelect?: (step: AgentWorkStepView) => void;
}

export function ToolCallCard({
  step,
  selected = false,
  pageUrl,
  products = [],
  onSelect,
}: ToolCallCardProps) {
  const stepRunning = isAgentRunningState(step.status.state);

  return (
    <Card
      size="sm"
      className={cn(
        "gap-0 overflow-visible bg-background/70 py-0 ring-0",
        selected && "ring-2 ring-sky-400/50",
        stepRunning && "ring-2 ring-sky-400/35",
      )}
    >
      <CardContent className="p-0">
        <Button
          type="button"
          variant="ghost"
          className="h-auto w-full items-start justify-between gap-3 rounded-xl px-2.5 py-2 text-left whitespace-normal"
          onClick={() => onSelect?.(step)}
        >
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-foreground">{step.label}</p>
            {step.hint ? (
              <p className="mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-all text-[11px] text-muted-foreground">
                {step.hint}
              </p>
            ) : null}
            {pageUrl ? (
              <Badge
                variant="link"
                className="mt-1 h-auto max-w-full justify-start gap-1 px-0 text-[11px] font-normal"
                render={<a href={pageUrl} target="_blank" rel="noopener noreferrer" />}
                onClick={(event) => event.stopPropagation()}
              >
                <ExternalLink className="size-3 shrink-0" />
                <span className="truncate">{pageUrl}</span>
              </Badge>
            ) : null}
          </div>
          <WorkStatusBadge
            label={step.status.label}
            badgeClass={step.status.badge_class}
            hint={step.status.hint}
          />
        </Button>
        {products.length > 0 ? (
          <ProductCardStrip items={products.map(toProductCardItem)} />
        ) : null}
      </CardContent>
    </Card>
  );
}
