import { agentStore } from "./agent-store";
import { MOCK_ANALYSIS, MOCK_PRODUCTS } from "./mock-data";
import type { AgentEvent, AgentStep } from "./types";

const timers = new Map<string, number[]>();

function schedule(runId: string, delay: number, event: AgentEvent) {
  const id = window.setTimeout(() => {
    agentStore.getState().applyEvent(event);
  }, delay);
  const list = timers.get(runId) ?? [];
  list.push(id);
  timers.set(runId, list);
}

export function cancelMockRun(runId: string) {
  const list = timers.get(runId) ?? [];
  for (const id of list) {
    window.clearTimeout(id);
  }
  timers.delete(runId);
}

/** 模拟完整 Agent 执行流（Phase 1）。 */
export function startMockAgentRun(runId: string, query: string) {
  cancelMockRun(runId);
  const started = Date.now();

  const steps: AgentStep[] = [
    { id: "s1", type: "search", title: "搜索商品", status: "pending" },
    { id: "s2", type: "process", title: "获取商品数据", status: "pending" },
    { id: "s3", type: "process", title: "数据清洗与去重", status: "pending" },
    { id: "s4", type: "analysis", title: "价格分析", status: "pending" },
    { id: "s5", type: "report", title: "生成分析报告", status: "pending" },
  ];

  let t = 0;
  schedule(runId, t, { type: "run.started", runId });
  schedule(runId, (t += 200), { type: "progress.updated", progress: 5, message: "准备执行" });

  schedule(runId, (t += 400), {
    type: "step.started",
    step: { ...steps[0]!, status: "running", startedAt: Date.now() },
  });
  schedule(runId, (t += 300), {
    type: "tool.started",
    runId,
    tool: {
      id: "tool-search",
      runId,
      tool: "search_xianyu",
      args: {
        keyword: query.slice(0, 40) || "iPhone 15 Pro Max 256GB",
        platform: "闲鱼",
      },
      status: "running",
      startedAt: Date.now(),
    },
  });
  schedule(runId, (t += 1200), {
    type: "tool.finished",
    runId,
    toolId: "tool-search",
    result: { count: 328, durationMs: 1200 },
  });
  schedule(runId, (t += 100), {
    type: "step.updated",
    stepId: "s1",
    data: { status: "success", finishedAt: Date.now(), duration: 1.5 },
  });
  schedule(runId, (t += 100), { type: "progress.updated", progress: 25, message: "搜索完成" });

  schedule(runId, (t += 300), {
    type: "step.started",
    step: { ...steps[1]!, status: "running", startedAt: Date.now() },
  });

  MOCK_PRODUCTS.forEach((product, index) => {
    schedule(runId, (t += 350 + index * 280), { type: "product.found", product });
    schedule(runId, t, {
      type: "progress.updated",
      progress: Math.min(55, 25 + (index + 1) * 5),
      message: `已发现 ${index + 1} 个商品`,
    });
  });

  schedule(runId, (t += 400), {
    type: "step.updated",
    stepId: "s2",
    data: { status: "success", finishedAt: Date.now() },
  });
  schedule(runId, (t += 200), {
    type: "step.started",
    step: { ...steps[2]!, status: "running", startedAt: Date.now() },
  });
  schedule(runId, (t += 800), {
    type: "step.updated",
    stepId: "s2",
    data: { status: "success", finishedAt: Date.now() },
  });
  schedule(runId, (t += 100), {
    type: "step.updated",
    stepId: "s3",
    data: { status: "success", finishedAt: Date.now() },
  });
  schedule(runId, (t += 200), { type: "progress.updated", progress: 65, message: "清洗完成" });

  schedule(runId, (t += 300), {
    type: "step.started",
    step: { ...steps[3]!, status: "running", startedAt: Date.now() },
  });
  schedule(runId, (t += 1000), {
    type: "analysis.updated",
    data: {
      priceBuckets: MOCK_ANALYSIS.priceBuckets,
      distribution: MOCK_ANALYSIS.distribution,
    },
  });
  schedule(runId, (t += 500), {
    type: "step.updated",
    stepId: "s4",
    data: { status: "success", finishedAt: Date.now() },
  });
  schedule(runId, (t += 200), { type: "progress.updated", progress: 85, message: "价格分析完成" });

  schedule(runId, (t += 300), {
    type: "step.started",
    step: { ...steps[4]!, status: "running", startedAt: Date.now() },
  });
  schedule(runId, (t += 600), {
    type: "analysis.updated",
    data: {
      summary: MOCK_ANALYSIS.summary,
      recommendedRange: MOCK_ANALYSIS.recommendedRange,
      recommendation: MOCK_ANALYSIS.recommendation,
    },
  });

  const reply =
    "已完成 iPhone 15 Pro Max 256GB 闲鱼比价分析。99新商品数量最多，价格集中在 ¥7,200 - ¥8,200，推荐优先考虑成色与卖家信誉较好的商品。";
  for (let i = 0; i < reply.length; i += 8) {
    schedule(runId, (t += 80), {
      type: "message.delta",
      runId,
      content: reply.slice(i, i + 8),
    });
  }

  schedule(runId, (t += 300), {
    type: "step.updated",
    stepId: "s5",
    data: { status: "success", finishedAt: Date.now(), duration: (Date.now() - started) / 1000 },
  });
  schedule(runId, (t += 100), { type: "progress.updated", progress: 100 });
  schedule(runId, (t += 100), { type: "run.finished", runId });
}
