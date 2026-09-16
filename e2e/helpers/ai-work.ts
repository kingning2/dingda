/**
 * AI 工作（找商品）链路的测试侧辅助。
 *
 * 与 `helpers/account.ts` / `helpers/agent.ts` 同一路数：跑在**测试进程**里直连被测壳
 * 拉起的 Server，只做「页面动作之后独立取证」，**绝不**用它推进流程 —— 发起一次 AI
 * 运行必须点页面上的发送按钮（见 specs/ai-product-search.spec.ts 的驱动原则）。
 *
 * 相关接口见 `packages-py/api/src/api/agent.py`：
 *   GET /v1/agent/works/{work_id} → 已持久化的 AI 工作快照（含 products / comparison）
 *
 * 为什么可以拿它当判据：`ui-ai/src/chat/use-work-detail.ts` 在 `can_send` 为真时会
 * flush 持久化（PUT 同一个接口），所以「一轮跑完」之后库里的 detail 就是最终态，
 * 而不是流水线中途的快照。也正因为如此，取它**必须等页面状态先落到 can_send**。
 */

/** 一条已采集商品（`contracts/crawler.ts` 的 `CrawlProductItem` 的子集）。 */
export type WorkProductItem = {
  id: string;
  title: string;
  price?: string;
  platform?: string;
  seller?: string | null;
  product_url?: string | null;
};

/** 结果面板的汇总视图（对应 `contracts/ai-work.ts` 的 `AgentWorkProductsView`）。 */
export type WorkProductsView = {
  items: WorkProductItem[];
  total: number;
  status?: { state: string; label: string; hint?: string | null };
};

/**
 * 持久化的工作快照（前端 `AgentWorkDetailView` 序列化后的形状）。
 *
 * 只声明本层要用到的字段，其余一概不关心 —— 这是前端自己的落库格式，
 * 后端原样存取（`works_repo`），没有服务端 schema 可依，别在这里补全量类型。
 */
export type WorkDetailSnapshot = {
  work_id?: string;
  can_send?: boolean;
  composer_agent_id?: string | null;
  composer_model_id?: string | null;
  status?: { state: string; label: string; hint?: string | null };
  products?: WorkProductsView;
  comparison?: { kind?: string; items?: unknown[] } | null;
  messages?: Array<{ role: string; content: string }>;
  /** 浏览器历史帧（含截图）；有值说明跑通过直播/截图链路。 */
  browser_history?: Array<{
    id?: string;
    url?: string;
    title?: string;
    screenshot_url?: string | null;
  }>;
};

async function getJson<T>(port: number, urlPath: string, timeoutMs = 10_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://127.0.0.1:${port}${urlPath}`, {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`GET ${urlPath} 返回 HTTP ${response.status}`);
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 读某个 AI 工作的落库快照；不存在（404）时返回 null。
 *
 * 404 是正常态：刚跳到 work 页、后端还没收到第一次 PUT 时就是 404，
 * 所以轮询方要能容忍 null，不要一上来就判失败。
 */
export async function fetchWorkDetail(
  port: number,
  workId: string,
): Promise<WorkDetailSnapshot | null> {
  try {
    const payload = await getJson<{ detail?: WorkDetailSnapshot }>(
      port,
      `/v1/agent/works/${encodeURIComponent(workId)}`,
    );
    return payload.detail ?? null;
  } catch {
    return null;
  }
}

/** 快照里最后一条助手正文；用于失败时说明「AI 到底回了个啥」。 */
export function lastAssistantText(detail: WorkDetailSnapshot | null): string {
  const messages = detail?.messages ?? [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role === "assistant" && message.content?.trim()) {
      return message.content.trim().slice(0, 500);
    }
  }
  return "";
}
