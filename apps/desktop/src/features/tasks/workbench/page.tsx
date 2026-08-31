/**
 * 商品比价 Agent 工作台 — 三栏 Event-driven UI（Phase 1 Mock）。
 */

import { useCallback } from "react";

import { AgentWorkspace } from "../components/agent/agent-workspace";
import { ProductDetailDialog } from "../components/product/product";
import { useAgentStore } from "./agent-store";
import { AnalysisWorkbenchPanel } from "./analysis-panel";
import { ConversationSidebar } from "./conversation-sidebar";
import { cancelMockRun, startMockAgentRun } from "./mock-agent";

export function WorkbenchPage() {
  const activeConversation = useAgentStore((state) => state.activeConversation());
  const activeRun = useAgentStore((state) => state.activeRun());
  const sendUserMessage = useAgentStore((state) => state.sendUserMessage);
  const stopRun = useAgentStore((state) => state.stopRun);
  const setSelectedProduct = useAgentStore((state) => state.setSelectedProduct);
  const selectedProductId = useAgentStore((state) => state.selectedProductId);

  const selectedProduct =
    activeRun?.products.find((item) => item.id === selectedProductId) ?? null;

  const handleSend = useCallback(
    (text: string) => {
      const runId = sendUserMessage(text);
      if (runId) {
        startMockAgentRun(runId, text);
      }
    },
    [sendUserMessage],
  );

  const handleStop = useCallback(() => {
    const run = useAgentStore.getState().activeRun();
    if (run) {
      cancelMockRun(run.id);
    }
    stopRun();
  }, [stopRun]);

  const title = activeConversation?.title ?? "新对话";
  const running = activeRun?.status === "running";

  return (
    <div className="flex h-full min-h-0 flex-1 overflow-hidden bg-background">
      <ConversationSidebar />

      <div className="flex min-w-0 flex-[1.1] flex-col overflow-hidden">
        <AgentWorkspace
          title={title}
          messages={activeRun?.messages ?? []}
          steps={activeRun?.steps ?? []}
          toolCalls={activeRun?.toolCalls ?? []}
          products={activeRun?.products ?? []}
          progress={activeRun?.progress ?? 0}
          progressMessage={activeRun?.progressMessage}
          running={running}
          onSend={handleSend}
          onStop={handleStop}
          onProductSelect={(product) => setSelectedProduct(product.id)}
        />
      </div>

      <AnalysisWorkbenchPanel
        run={activeRun}
        onProductSelect={setSelectedProduct}
      />

      <ProductDetailDialog
        product={selectedProduct}
        open={selectedProductId != null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedProduct(null);
          }
        }}
      />
    </div>
  );
}
