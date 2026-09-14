/**
 * 后端消息 → 渲染轮次。
 *
 * 职责：
 *   把 `AgentWorkDetailView.messages` 翻译成 `ChatTurn[]`，即「聊天记录怎么排」。
 *
 * 设计说明：
 *   - 纯函数：不依赖 React、不依赖 DOM，可以给定 detail 直接断言输出的块序列。
 *   - 活回合与历史回放走同一条路径，区别只在 `busy` / `phase` 两个入参。
 *   - `timeline` 是**交错**的（思考 ↔ 工具 ↔ 正文），所以逐条按 kind 分派，
 *     不按类型分组 —— 分组会丢掉到达顺序。
 *   - 不猜后端语义：步骤块的 kind / page / status 全部来自后端下发的 step，
 *     前端只做「按 id 查回来」这一件事。
 */

import type {
  AgentWorkDetailView,
  AgentWorkMessageView,
  AgentWorkProductItem,
  AgentWorkStepView,
  AgentWorkTimelineEntry,
} from "@v2/contracts/ai-work";
import { AGENT_RUN_PHASE_MAP, type AgentRunPhase } from "@v2/ui-agent/agent-run-phase";
import type { ChatBlock, ChatBlockOf, ChatTurn } from "./types";

/** 一个步骤挂着的商品。 */
function productsForStep(items: AgentWorkProductItem[], stepId: string): AgentWorkProductItem[] {
  return items.filter((item) => item.step_id === stepId);
}

/**
 * 步骤对应的页面地址：优先当前直播帧，回落历史帧。
 *
 * 直播帧会随步骤切换而变，所以只有 `frame_id` 相等才说明「现在直播的就是这一步」。
 * 不比 id 会让所有历史步骤都显示当前页面的 url。
 */
function resolveStepPageUrl(detail: AgentWorkDetailView, step: AgentWorkStepView): string | null {
  // 只有爬虫类步骤才关联网页；工具类步骤（执行命令等）没有 frame。
  if (!step.browser_frame_id) return null;
  if (detail.browser_live.frame_id === step.browser_frame_id) {
    const url = detail.browser_live.url;
    // about:blank 是浏览器初始空页（session.ts 的空壳里就写着这个值），
    // 直接显示没有意义 —— 用户会看到字面的 about:blank。
    return url && url !== "about:blank" ? url : null;
  }
  return detail.browser_history.find((item) => item.id === step.browser_frame_id)?.url ?? null;
}

/**
 * 新格式：按 timeline 条目顺序铺开（思考 ↔ 工具 ↔ 正文交错）。
 *
 * 这是「逐层展开」而不是递归 —— 目前最深处只有 3 层（消息 → timeline 条目 → 块），
 * 循环比递归清楚。若将来 timeline 支持嵌套（如子 Agent 的子时间线），再换递归。
 */
function fromTimeline(
  messageId: string,
  timeline: AgentWorkTimelineEntry[],
  steps: AgentWorkStepView[],
  detail: AgentWorkDetailView,
  phase: AgentRunPhase | null,
  meta: { startedAt?: string | null; durationSec?: number | null },
): ChatBlock[] {
  const lastIndex = timeline.length - 1;
  // 当前阶段真正在流入的块类型；phase 为 null（不在运行中）时没有任何块该流式。
  // 从映射表取而不是自己判断阶段名 —— agent-run-phase.ts 明写「新增阶段时只改这里」。
  const streamingKind = phase ? AGENT_RUN_PHASE_MAP[phase].streamingKind : null;
  const out: ChatBlock[] = [];

  for (let i = 0; i < timeline.length; i++) {
    const entry = timeline[i];
    const isLast = i === lastIndex;

    // 三个条件缺一不可，各管一件事：
    //   ① streamingKind 非空 —— 当前阶段确实有块在流入
    //      （executing / live / products 三个阶段为 null，工具执行时没有文字在流入）
    //   ② isLast —— 只有最末一个块流式；历史块不能重播打字动画
    //   ③ 类型匹配 —— 块类型要和阶段一致，否则上一轮残留的 text 会跟着流式
    const live = Boolean(streamingKind) && isLast && entry.kind === streamingKind;

    if (entry.kind === "thinking") {
      out.push({
        kind: "thinking",
        id: `${messageId}-${entry.id}`,
        text: entry.text,
        streaming: live,
        startedAt: meta.startedAt,
        // 思考时长属于整轮，不属于每一段 —— 只有最末块带它。
        durationSec: isLast ? (meta.durationSec ?? null) : null,
      });
      continue;
    }

    if (entry.kind === "step") {
      // timeline 只存 step 的 id，步骤本体（label / status / page）在 message.steps 里
      // —— 规范化：同一份数据不存两处，避免更新时不一致。所以这里按 id 查回来。
      const step = steps.find((item) => item.id === entry.id);
      // 查不到就跳过：后端格式演进过，老库里的 timeline 条目可能对不上现在的 steps。
      // 此时少渲染一个块，而不是让整页抛错。
      if (!step) continue;
      out.push({
        kind: "step",
        id: `${messageId}-step-${step.id}`,
        step,
        pageUrl: resolveStepPageUrl(detail, step),
        products: productsForStep(detail.products.items, step.id),
      });
      continue;
    }

    out.push({ kind: "text", id: `${messageId}-${entry.id}`, text: entry.text, streaming: live });
  }

  return out;
}

/** 旧格式：没有 timeline，按 thinking → steps → content 固定顺序铺开。 */
function fromLegacy(
  message: AgentWorkMessageView,
  detail: AgentWorkDetailView,
  phase: AgentRunPhase | null,
): ChatBlock[] {
  const streamingKind = phase ? AGENT_RUN_PHASE_MAP[phase].streamingKind : null;
  const out: ChatBlock[] = [];
  // trim 后再判：后端可能给 "\n" 这类只有空白的字段，
  // 不 trim 会渲染出一个空块，在时间线上留出空白间隙。
  const thinking = (message.thinking ?? "").trim();

  if (thinking) {
    out.push({
      kind: "thinking",
      id: `${message.id}-thinking`,
      text: thinking,
      streaming: streamingKind === "thinking",
      startedAt: message.thinking_started_at ?? message.created_at,
      durationSec: message.thinking_duration_sec ?? null,
    });
  }

  for (const step of message.steps ?? []) {
    out.push({
      kind: "step",
      id: `${message.id}-step-${step.id}`,
      step,
      pageUrl: resolveStepPageUrl(detail, step),
      products: productsForStep(detail.products.items, step.id),
    });
  }

  if (message.content?.trim()) {
    out.push({
      kind: "text",
      id: `${message.id}-text`,
      text: message.content,
      streaming: streamingKind === "text",
    });
  }

  return out;
}

/**
 * 单条消息 → 有序块。
 *
 * `type` 不单独传参，而是收进判别联合的 `kind` 字段 —— 两个参数容易传错位，一个对象不会。
 */
export function scheduleMessage(
  message: AgentWorkMessageView,
  detail: AgentWorkDetailView,
  streaming: boolean,
  phase: AgentRunPhase | null = null,
): ChatBlock[] {
  // 守卫子句：用户消息没有 timeline / steps / thinking，走下面的逻辑全是空转。
  // 早返回的真正价值是让后续代码可以「假定这是助手消息」，不必再判一次 role。
  if (message.role === "user") {
    return [
      {
        kind: "user",
        id: `user-${message.id}`,
        messageId: message.id,
        content: message.content,
        attachments: message.attachments,
      },
    ];
  }

  // 新格式（timeline）与旧格式（平铺 thinking / steps / content）分流。
  // 判据用 timeline 长度而非「有没有 thinking」：timeline 是唯一能表达交错顺序的结构，
  // 只要它有内容就必须用它，否则退化成旧格式的固定顺序，交错信息全丢。
  // 不判这个分支：老会话（库里只有旧字段）会渲染成空白。
  const timeline = message.timeline ?? [];
  if (timeline.length > 0) {
    return fromTimeline(
      message.id,
      timeline,
      message.steps ?? [],
      detail,
      streaming ? phase : null,
      {
        startedAt: message.thinking_started_at ?? message.created_at,
        durationSec: message.thinking_duration_sec ?? null,
      },
    );
  }
  return fromLegacy(message, detail, streaming ? phase : null);
}

/**
 * 整条记录 → 可渲染轮次。
 *
 * 轮次的边界由**用户消息**定义：遇到用户消息开新轮，助手块挂到「当前轮」。
 * 不判 role 的话助手块会挂错轮，sticky 分区直接失效。
 */
export function scheduleTurns(
  detail: AgentWorkDetailView,
  busy: boolean,
  phase: AgentRunPhase | null = null,
): ChatTurn[] {
  const lastAssistantId = [...detail.messages].reverse().find((m) => m.role === "assistant")?.id;
  const turns: ChatTurn[] = [];
  let current: ChatTurn | null = null;

  for (const message of detail.messages) {
    // 只有最末一条助手消息处于流式；历史消息一律静态铺开。
    // 不加 id 比较：一次运行期间会话里可能有 10 条助手消息，
    // 全部被打上 streaming 后 useRevealText 会把整段历史逐字重播。
    const streaming = busy && message.id === lastAssistantId && message.role === "assistant";
    const scheduled = scheduleMessage(message, detail, streaming, streaming ? phase : null);

    if (message.role === "user") {
      const user = scheduled.find(
        (block): block is ChatBlockOf<"user"> => block.kind === "user",
      );
      // 这不是运行时防御，是「用一个 if 换掉一个 `!`」：
      // find 返回 T | undefined，不判就得写 `!`，而 `!` 一旦落空会让整页抛错白屏；
      // 判一下只是跳过这一轮。
      if (!user) continue;
      current = { id: `turn-${message.id}`, user, blocks: [] };
      turns.push(current);
      continue;
    }

    // 没有前置用户消息的助手块（数据异常）单独成轮，宁可显示得奇怪也不要丢内容。
    if (current) current.blocks.push(...scheduled);
    else turns.push({ id: `orphan-${turns.length}`, user: null, blocks: scheduled });
  }

  return turns;
}

/**
 * 按运行阶段裁剪块：思考阶段隐藏尚未被后续事件替代的正文。
 *
 * 工具、直播和商品块始终保留 —— 它们表达的是「已经发生了什么」，不该随阶段消失。
 */
export function blocksForPhase(blocks: ChatBlock[], phase: AgentRunPhase | null): ChatBlock[] {
  if (!phase || !AGENT_RUN_PHASE_MAP[phase].hideTextWhileThinking) return blocks;
  let lastThinking = -1;
  let lastText = -1;
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    if (block.kind === "thinking") lastThinking = i;
    if (block.kind === "text") lastText = i;
  }
  if (lastThinking > lastText) {
    return blocks.filter((block) => block.kind !== "text");
  }
  return blocks;
}
