/**
 * 聊天记录编排测试。
 *
 * `schedule.ts` 是纯函数（不依赖 React、不依赖 DOM），所以这里直接给定 detail
 * 断言输出的块序列 —— 这正是把它从组件里抽出来的理由。
 *
 * 覆盖重点是三类容易写错、且出错后**不报错只是少渲染**的地方：
 *   1. timeline 的交错顺序（按类型分组就会丢顺序）
 *   2. 流式标记的三个条件（只有最末块 / 类型要匹配 / busy=false 时不重播）
 *   3. 新旧格式分流与异常数据（老会话没有 timeline；孤儿助手消息不能丢）
 */
import { describe, expect, it } from "vitest";

import { blocksForPhase, scheduleMessage, scheduleTurns } from "@v2/ui-ai/chat/schedule";
import type { ChatBlock } from "@v2/ui-ai/chat/types";

/**
 * 按 kind 取块并收窄类型。
 *
 * `Array.find` 返回的是 `ChatBlock | undefined` 联合类型，直接取变体字段
 * （如 `pageUrl`）会被 tsc 拦 —— 这个 helper 比在每处写 `as` 断言更能说明意图。
 */
function blockOf<K extends ChatBlock["kind"]>(blocks: ChatBlock[], kind: K) {
  return blocks.find((block): block is Extract<ChatBlock, { kind: K }> => block.kind === kind);
}

const status = { state: "ready", label: "已完成", hint: null, badge_class: "b" };

const step = {
  id: "s1",
  label: "抓取",
  kind: "browser_crawl",
  status,
  browser_frame_id: "s1",
  page: { url: "https://x.test/a", title: "页", screenshot_url: "s.png", loading: false },
};
const toolStep = { id: "s2", label: "命令", kind: "tool", status };

const assistant = (over: Record<string, unknown>) => ({
  id: "a1",
  role: "assistant",
  content: "",
  created_at: "2026-01-01T00:00:00Z",
  ...over,
});

const detail = (messages: unknown[]) =>
  ({
    work_id: "w1",
    title: "t",
    status,
    messages,
    products: {
      items: [{ id: "p1", title: "商品", step_id: "s1", platform: "xianyu", price: "1" }],
      total: 1,
      status,
    },
    recommendations: { items: [], total: 0, status, summary: null },
    comparison: null,
    browser_live: {
      frame_id: "s1",
      url: "https://x.test/live",
      title: "直播",
      status,
      progress_hint: null,
      focus_label: null,
    },
    browser_history: [{ id: "f9", url: "https://x.test/old", title: "旧" }],
    composer_placeholder: "",
    can_send: true,
    cli_session_id: null,
    cli_session_runtime_id: null,
    composer_agents: [],
    composer_agent_id: "codex",
    composer_model_id: null,
  }) as never;

/** 标准样本：思考 → 工具 → 正文，交错排列。 */
const timelineMessage = assistant({
  content: "答案",
  thinking: "想",
  thinking_started_at: "2026-01-01T00:00:01Z",
  thinking_duration_sec: 3,
  steps: [step, toolStep],
  timeline: [
    { kind: "thinking", id: "t0", text: "想" },
    { kind: "step", id: "s1" },
    { kind: "text", id: "x0", text: "答案" },
  ],
});
const timelineDetail = detail([
  { id: "u1", role: "user", content: "问题", created_at: "2026-01-01T00:00:00Z" },
  timelineMessage,
]);

describe("轮次切分", () => {
  it("一轮 = 一条用户消息 + 其后全部助手块", () => {
    const turns = scheduleTurns(timelineDetail, false, null);
    expect(turns).toHaveLength(1);
    expect(turns[0]?.user?.content).toBe("问题");
    expect(turns[0]?.user?.messageId).toBe("u1");
    expect(turns[0]?.blocks.map((b) => b.kind)).toEqual(["thinking", "step", "text"]);
  });

  it("两条用户消息切成两轮，助手块各归其轮", () => {
    const turns = scheduleTurns(
      detail([
        { id: "u1", role: "user", content: "一", created_at: "x" },
        assistant({ id: "a1", content: "答一", timeline: [{ kind: "text", id: "x1", text: "答一" }] }),
        { id: "u2", role: "user", content: "二", created_at: "x" },
        assistant({ id: "a2", content: "答二", timeline: [{ kind: "text", id: "x2", text: "答二" }] }),
      ]),
      false,
      null,
    );
    expect(turns).toHaveLength(2);
    expect(turns[0]?.blocks).toHaveLength(1);
    expect(turns[1]?.user?.content).toBe("二");
    expect(turns[1]?.blocks).toHaveLength(1);
  });

  it("孤儿助手消息单独成轮，不丢内容", () => {
    const turns = scheduleTurns(
      detail([assistant({ id: "a6", timeline: [{ kind: "text", id: "x2", text: "孤儿" }] })]),
      false,
      null,
    );
    expect(turns).toHaveLength(1);
    expect(turns[0]?.user).toBeNull();
    expect(turns[0]?.blocks).toHaveLength(1);
  });
});

describe("timeline：按到达顺序铺开", () => {
  it("交错顺序不按类型分组", () => {
    const blocks = scheduleMessage(timelineMessage as never, timelineDetail, false, null);
    expect(blocks.map((b) => b.id)).toEqual(["a1-t0", "a1-step-s1", "a1-x0"]);
  });

  it("步骤块带上 step_id 匹配的商品", () => {
    const blocks = scheduleMessage(timelineMessage as never, timelineDetail, false, null);
    const s = blockOf(blocks, "step");
    expect(s?.products).toHaveLength(1);
    expect(s?.products[0]?.id).toBe("p1");
  });

  it("思考时长只挂在最末 thinking 块上（时长属于整轮）", () => {
    const two = assistant({
      id: "a2",
      timeline: [
        { kind: "thinking", id: "t0", text: "一" },
        { kind: "thinking", id: "t1", text: "二" },
      ],
      thinking_duration_sec: 5,
    });
    const blocks = scheduleMessage(two as never, timelineDetail, false, null);
    const [first, second] = blocks;
    expect(first?.kind === "thinking" && first.durationSec).toBeNull();
    expect(second?.kind === "thinking" && second.durationSec).toBe(5);
  });

  it("step id 在 steps 里查不到时跳过，不抛错", () => {
    const bad = assistant({
      id: "a5",
      timeline: [
        { kind: "step", id: "nope" },
        { kind: "text", id: "x1", text: "尾" },
      ],
    });
    const blocks = scheduleMessage(bad as never, timelineDetail, false, null);
    expect(blocks.map((b) => b.kind)).toEqual(["text"]);
  });
});

describe("步骤块的页面地址", () => {
  it("frame_id 相等时取直播帧", () => {
    const blocks = scheduleMessage(timelineMessage as never, timelineDetail, false, null);
    expect(blockOf(blocks, "step")?.pageUrl).toBe("https://x.test/live");
  });

  it("不在直播中的步骤回落历史帧", () => {
    const other = assistant({
      id: "a9",
      steps: [{ ...step, id: "s7", browser_frame_id: "f9" }],
      timeline: [{ kind: "step", id: "s7" }],
    });
    const blocks = scheduleMessage(other as never, timelineDetail, false, null);
    expect(blockOf(blocks, "step")?.pageUrl).toBe("https://x.test/old");
  });

  it("about:blank 视为无地址", () => {
    const blank = detail([]) as never as { browser_live: { url: string } };
    blank.browser_live.url = "about:blank";
    const blocks = scheduleMessage(timelineMessage as never, blank as never, false, null);
    expect(blockOf(blocks, "step")?.pageUrl).toBeNull();
  });
});

describe("流式标记", () => {
  it("busy=false 时无块流式（历史不重播打字动画）", () => {
    const turns = scheduleTurns(timelineDetail, false, "outputting");
    expect(turns[0]?.blocks.some((b) => "streaming" in b && b.streaming)).toBe(false);
  });

  it("phase=outputting 时只有最末 text 块流式", () => {
    const turns = scheduleTurns(timelineDetail, true, "outputting");
    const streaming = turns[0]?.blocks.filter((b) => "streaming" in b && b.streaming);
    expect(streaming).toHaveLength(1);
    expect(streaming?.[0]?.kind).toBe("text");
  });

  it("phase=thinking 但最末块是 text 时无块流式（类型要匹配）", () => {
    const turns = scheduleTurns(timelineDetail, true, "thinking");
    expect(turns[0]?.blocks.some((b) => "streaming" in b && b.streaming)).toBe(false);
  });

  it("phase=executing（streamingKind 为 null）时无块流式", () => {
    const turns = scheduleTurns(timelineDetail, true, "executing");
    expect(turns[0]?.blocks.some((b) => "streaming" in b && b.streaming)).toBe(false);
  });
});

describe("新旧格式分流", () => {
  it("无 timeline 走旧格式：thinking → steps → content", () => {
    const legacy = assistant({ id: "a3", content: "正文", thinking: " 想 ", steps: [toolStep] });
    const blocks = scheduleMessage(legacy as never, timelineDetail, false, null);
    expect(blocks.map((b) => b.kind)).toEqual(["thinking", "step", "text"]);
    expect(blocks[0]?.kind === "thinking" && blocks[0].text).toBe("想");
  });

  it("只有空白的 thinking / content 不产生块", () => {
    const blank = assistant({ id: "a4", content: "\n", thinking: "   " });
    expect(scheduleMessage(blank as never, timelineDetail, false, null)).toEqual([]);
  });
});

describe("blocksForPhase：思考阶段裁掉尚未被接替的正文", () => {
  const text = { kind: "text", id: "t1", text: "旧", streaming: false } as never;
  const thinking = { kind: "thinking", id: "k1", text: "想", streaming: true } as never;

  it("最后是 thinking 时隐藏 text", () => {
    expect(blocksForPhase([text, thinking], "thinking").map((b) => b.kind)).toEqual(["thinking"]);
  });

  it("最后是 text 时保留", () => {
    expect(blocksForPhase([thinking, text], "thinking").map((b) => b.kind)).toEqual([
      "thinking",
      "text",
    ]);
  });

  it("phase=null 时原样返回", () => {
    expect(blocksForPhase([text], null)).toHaveLength(1);
  });
});
