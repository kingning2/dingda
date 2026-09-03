import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { AgentRuntimeItem } from "@/contracts/agent-runtime";
import { loginAgentRuntime } from "@/lib/agent-runtime";
import { probeSingleAgent, rescanAgentRuntimes } from "@/lib/agent-runtime-scan";
import { Button } from "@/components/ui/button";
import { AgentRuntimeCard } from "./agent-runtime-card";
import {
  areAgentRuntimesEqual,
  getAgentRuntimes,
  mockSetDefaultAgent,
  setAgentRuntimes,
  subscribeAgentRuntimes,
} from "./agent-mock-data";

export function AgentRuntimesPanel() {
  const [agents, setAgents] = useState(getAgentRuntimes);
  const [scanning, setScanning] = useState(false);
  const [loggingInId, setLoggingInId] = useState<string | null>(null);
  const [actionHint, setActionHint] = useState<string | null>(null);

  useEffect(
    () =>
      subscribeAgentRuntimes(() => {
        const next = getAgentRuntimes();
        setAgents((prev) => (areAgentRuntimesEqual(prev, next) ? prev : next));
      }),
    [],
  );

  function commitAgents(next: AgentRuntimeItem[]) {
    setAgentRuntimes(next);
    setAgents(next);
  }

  const installed = agents.filter((agent) => agent.available);
  const missing = agents.filter((agent) => !agent.available);

  async function handleRescan() {
    setScanning(true);
    setActionHint(null);
    commitAgents(await rescanAgentRuntimes());
    setScanning(false);
  }

  async function handleLogin(agent: AgentRuntimeItem) {
    setLoggingInId(agent.id);
    setActionHint(null);
    const result = await loginAgentRuntime(agent.id);
    setActionHint(result.message);
    if (result.started) {
      probeSingleAgent(agent.id);
    }
    setLoggingInId(null);
  }

  function handleSetDefault(agentId: string) {
    commitAgents(mockSetDefaultAgent(agents, agentId));
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          请按各工具官方文档自行安装 Agent CLI，安装完成后点击右上角「扫描 Agent」重新检测并刷新可用模型。
        </p>
        <Button size="sm" variant="outline" disabled={scanning} onClick={() => void handleRescan()}>
          <RefreshCw className={scanning ? "size-4 animate-spin" : "size-4"} />
          {scanning ? "扫描中…" : "扫描 Agent"}
        </Button>
      </div>

      {actionHint ? (
        <p className="rounded-md border border-border/70 bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          {actionHint}
        </p>
      ) : null}

      {installed.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-medium">已检测到（{installed.length}）</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {installed.map((agent) => (
              <AgentRuntimeCard
                key={agent.id}
                agent={agent}
                loggingIn={loggingInId === agent.id}
                onLogin={() => void handleLogin(agent)}
                onSetDefault={() => handleSetDefault(agent.id)}
              />
            ))}
          </div>
        </section>
      ) : null}

      {missing.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-medium">未安装（{missing.length}）</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {missing.map((agent) => (
              <AgentRuntimeCard key={agent.id} agent={agent} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
