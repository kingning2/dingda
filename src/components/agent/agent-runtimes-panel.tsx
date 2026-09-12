import { useState } from "react";
import { RefreshCw } from "lucide-react";
import type { AgentRuntimeItem } from "@v2/contracts/agent-runtime";
import {
  applyAgentPreferences,
  downloadAgentRuntime,
  loginAgentRuntime,
} from "@/lib/agent-runtime";
import { putDefaultAgentId, putDefaultModelId } from "@/lib/agent-api";
import { probeSingleAgent, rescanAgentRuntimes } from "@/lib/discovery-scan";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { useServer } from "@/providers/server-provider";
import { Button } from "@v2/ui-primitives/button";
import { AgentRuntimeCard } from "./agent-runtime-card";

export function AgentRuntimesPanel() {
  const server = useServer();
  const agents = useDiscoveryStore((state) => state.agents);
  const scanning = useDiscoveryStore((state) => state.agentsScanning);
  const setAgents = useDiscoveryStore((state) => state.setAgents);
  const [loggingInId, setLoggingInId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [actionHint, setActionHint] = useState<string | null>(null);

  const installed = agents.filter((agent) => agent.available);
  const missing = agents.filter((agent) => !agent.available);

  async function handleRescan() {
    setActionHint(null);
    await rescanAgentRuntimes(server.apiBaseUrl);
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

  async function handleDownload(agent: AgentRuntimeItem) {
    setDownloadingId(agent.id);
    setActionHint(null);
    try {
      const result = await downloadAgentRuntime(agent.id);
      setActionHint(`${result.message}${result.version ? `（${result.version}）` : ""}`);
      probeSingleAgent(agent.id);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setActionHint(message);
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleSetDefault(agentId: string) {
    setActionHint(null);
    if (!server.ready) {
      setActionHint("服务未就绪，无法保存默认 Agent");
      return;
    }
    try {
      const saved = await putDefaultAgentId(agentId);
      setAgents(applyAgentPreferences(agents, { default_agent_id: saved }));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setActionHint(message);
    }
  }

  async function handlePreferredModelChange(agentId: string, modelId: string) {
    setActionHint(null);
    setAgents(
      agents.map((agent) =>
        agent.id === agentId ? { ...agent, preferred_model_id: modelId } : agent,
      ),
    );
    if (!server.ready) {
      setActionHint("服务未就绪，模型选择仅本次有效");
      return;
    }
    try {
      await putDefaultModelId(agentId, modelId);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setActionHint(message);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          每个 Agent 共用同一张配置卡：下载/安装 CLI → 登录或配置 API →
          选模型。支持托管下载的可一键装到叮答目录；其余按文档安装后点「扫描 Agent」。
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
                onSetDefault={() => void handleSetDefault(agent.id)}
                onPreferredModelChange={(modelId) =>
                  void handlePreferredModelChange(agent.id, modelId)
                }
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
              <AgentRuntimeCard
                key={agent.id}
                agent={agent}
                downloading={downloadingId === agent.id}
                onDownload={
                  agent.can_download ? () => void handleDownload(agent) : undefined
                }
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
