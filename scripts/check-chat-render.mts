/**
 * 聊天渲染与工具输出解析的行为检查。
 *
 * 职责：
 *   用真实数据跑一遍 `ui-ai/chat/schedule`、`agent-output` 与 `runtime/guards`，
 *   断言输出的块序列、流式标记、轮次切分与字段容错结果。
 *
 * 为什么需要它（不是可有可无）：
 *   前端没有单测框架，而这几处是**纯函数**，出错的形态是「静默少渲染」而不是报错 ——
 *   本脚本第一次跑就抓到 `isArray(items, [])` 因候选语义颠倒而返回兜底值，
 *   导致商品 / 比价 / comments 全被清空。这类 bug 靠肉眼看 diff 发现不了。
 *
 * 用法：
 *   ./node_modules/.bin/tsx scripts/check-chat-render.mts
 *   或 `pnpm check:chat-render`
 *
 * 已知依赖问题（待处理）：
 *   本脚本靠 `tsx` 执行，而 `tsx` **没有在任何 package.json 里声明** ——
 *   它是 vite / @tailwindcss/vite 的**可选 peer 依赖**，被 pnpm 提升到了
 *   `node_modules/.bin`。能跑，但属幻影依赖：哪天 vite 去掉这个 optional peer
 *   就会失效。正规做法是把 `tsx` 加进根 devDependencies（需 `pnpm install`），
 *   或整体换成 vitest —— 那是项目测试策略的决定，留给用户拍板。
 *
 * 注意：`scripts/` 不在根 tsconfig 的 include 内，所以本文件不参与 `tsc --noEmit`，
 * 也不会被 `check-unused.mjs` 扫到（与其它 `scripts/*.mjs` 一致）。
 */
import assert from "node:assert/strict";

import { isArray, isBoolean, isFunction, isNumber, isObject, isString } from "@v2/runtime/guards";
import { blocksForPhase, scheduleMessage, scheduleTurns } from "@v2/ui-ai/chat/schedule";
import {
  extractComparison,
  extractProducts,
  mergeComparison,
  mergeProducts,
} from "@v2/ui-ai/agent-output";

let passed = 0;
const ok = (name: string, fn: () => void) => {
  try {
    fn();
    passed += 1;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    console.log(`  ✗ ${name}`);
    console.log(`      ${err instanceof Error ? err.message.split("\n")[0] : String(err)}`);
    process.exitCode = 1;
  }
};

const status = { state: "ready", label: "已完成", hint: null, badge_class: "b" };
const running = { state: "running", label: "执行中", hint: null, badge_class: "b" };

const step = {
  id: "s1",
  label: "抓取",
  kind: "browser_crawl",
  status,
  browser_frame_id: "s1",
  page: { url: "https://x.test/a", title: "页", screenshot_url: "s.png", loading: false },
};
const toolStep = { id: "s2", label: "命令", kind: "tool", status };

const message = (over: Record<string, unknown>) => ({
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
    browser_live: { frame_id: "s1", url: "https://x.test/live", title: "直播", status, progress_hint: null, focus_label: null },
    browser_history: [{ id: "f9", url: "https://x.test/old", title: "旧" }],
    composer_placeholder: "",
    can_send: true,
    cli_session_id: null,
    cli_session_runtime_id: null,
    composer_agents: [],
    composer_agent_id: "codex",
    composer_model_id: null,
  }) as never;

console.log("\n[1] guards —— 判定 + 兜底 + 多候选");
ok("单值命中", () => assert.equal(isString("a", ""), "a"));
ok("单值不命中走兜底", () => assert.equal(isString(123, ""), ""));
ok("多候选取第一个命中的", () => assert.equal(isString([undefined, null, "b", "c"], ""), "b"));
ok("多候选全不命中走兜底", () => assert.equal(isString([1, 2], "z"), "z"));
ok("兜底 undefined 时返回 undefined", () => assert.equal(isString(1, undefined), undefined));
ok("isNumber 拒 NaN", () => assert.equal(isNumber(Number.NaN, null), null));
ok("isNumber 拒 Infinity", () => assert.equal(isNumber(Number.POSITIVE_INFINITY, null), null));
ok("isNumber 收 0", () => assert.equal(isNumber(0, null), 0));
ok("isNumber 不收数字字符串（判定不转换）", () => assert.equal(isNumber("12", null), null));
ok("isObject 拒 null", () => assert.equal(isObject(null, null), null));
ok("isObject 拒数组", () => assert.equal(isObject([], null), null));
ok("isObject 收普通对象", () => assert.deepEqual(isObject({ a: 1 }, null), { a: 1 }));
ok("isBoolean / isFunction", () => {
  assert.equal(isBoolean(true, false), true);
  assert.equal(isFunction(() => 1, null) instanceof Function, true);
});
ok("【边界】数组先整体、再逐元素", () => {
  // 整体满足判定就直接用它 —— 这是「取一个数组字段」的常见写法
  assert.deepEqual(isArray([1, 2], []), [1, 2]);
  assert.deepEqual(isArray([], []), []);
  // 整体不满足且是数组，才当候选列表逐元素找
  assert.equal(isString([1, 2], ""), "");
  assert.equal(isString([1, "b"], ""), "b");
  assert.deepEqual(isObject([{ a: 1 }], null), { a: 1 });
  assert.equal(isObject([], null), null);
});

console.log("\n[2] schedule —— 轮次切分与块顺序");
const tlMsg = message({
  id: "a1",
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
const tlDetail = detail([
  { id: "u1", role: "user", content: "问题", created_at: "2026-01-01T00:00:00Z" },
  tlMsg,
]);

ok("一轮 = 一条用户消息 + 其后助手块", () => {
  const turns = scheduleTurns(tlDetail, false, null);
  assert.equal(turns.length, 1);
  assert.equal(turns[0]!.user?.content, "问题");
  assert.equal(turns[0]!.user?.messageId, "u1");
  assert.deepEqual(
    turns[0]!.blocks.map((b) => b.kind),
    ["thinking", "step", "text"],
  );
});
ok("timeline 保持到达顺序（交错不分组）", () => {
  const blocks = scheduleMessage(tlMsg as never, tlDetail, false, null);
  assert.deepEqual(blocks.map((b) => b.id), ["a1-t0", "a1-step-s1", "a1-x0"]);
});
ok("步骤块带上匹配的商品", () => {
  const blocks = scheduleMessage(tlMsg as never, tlDetail, false, null);
  const s = blocks.find((b) => b.kind === "step");
  assert.equal(s?.products.length, 1);
  assert.equal(s?.products[0]?.id, "p1");
});
ok("步骤块取直播帧 url（frame_id 相等）", () => {
  const blocks = scheduleMessage(tlMsg as never, tlDetail, false, null);
  const s = blocks.find((b) => b.kind === "step");
  assert.equal(s?.pageUrl, "https://x.test/live");
});
ok("非直播步骤回落历史帧", () => {
  const other = message({ id: "a9", steps: [{ ...step, id: "s7", browser_frame_id: "f9" }], timeline: [{ kind: "step", id: "s7" }] });
  const blocks = scheduleMessage(other as never, tlDetail, false, null);
  assert.equal(blocks[0]?.pageUrl, "https://x.test/old");
});
ok("about:blank 视为无 url", () => {
  const d = { ...(tlDetail as never as Record<string, unknown>) } as never;
  (d as never as { browser_live: { url: string } }).browser_live.url = "about:blank";
  const blocks = scheduleMessage(tlMsg as never, d, false, null);
  assert.equal(blocks.find((b) => b.kind === "step")?.pageUrl, null);
});

console.log("\n[3] schedule —— 流式标记");
ok("busy=false 时无块流式（历史不重播）", () => {
  const turns = scheduleTurns(tlDetail, false, "outputting");
  assert.equal(turns[0]!.blocks.some((b) => b.kind === "text" && b.streaming), false);
});
ok("phase=outputting 时最末 text 块流式", () => {
  const turns = scheduleTurns(tlDetail, true, "outputting");
  const text = turns[0]!.blocks.find((b) => b.kind === "text");
  assert.equal(text?.streaming, true);
  assert.equal(turns[0]!.blocks.filter((b) => "streaming" in b && b.streaming).length, 1);
});
ok("phase=thinking 但最末块是 text 时无块流式（类型要匹配）", () => {
  const turns = scheduleTurns(tlDetail, true, "thinking");
  assert.equal(turns[0]!.blocks.some((b) => "streaming" in b && b.streaming), false);
});
ok("phase=executing（streamingKind 为 null）时无块流式", () => {
  const turns = scheduleTurns(tlDetail, true, "executing");
  assert.equal(turns[0]!.blocks.some((b) => "streaming" in b && b.streaming), false);
});
ok("思考时长只挂在最末 thinking 块上", () => {
  const two = message({
    id: "a2",
    steps: [],
    timeline: [
      { kind: "thinking", id: "t0", text: "一" },
      { kind: "thinking", id: "t1", text: "二" },
    ],
    thinking_duration_sec: 5,
  });
  const blocks = scheduleMessage(two as never, tlDetail, false, null);
  assert.equal(blocks[0]?.kind === "thinking" && blocks[0].durationSec, null);
  assert.equal(blocks[1]?.kind === "thinking" && blocks[1].durationSec, 5);
});

console.log("\n[4] schedule —— 新旧格式与异常数据");
ok("无 timeline 走旧格式：thinking → steps → content", () => {
  const legacy = message({ id: "a3", content: "正文", thinking: " 想 ", steps: [toolStep] });
  const blocks = scheduleMessage(legacy as never, tlDetail, false, null);
  assert.deepEqual(blocks.map((b) => b.kind), ["thinking", "step", "text"]);
  assert.equal(blocks[0]?.kind === "thinking" && blocks[0].text, "想");
});
ok("只有空白的 thinking / content 不产生块", () => {
  const blank = message({ id: "a4", content: "\n", thinking: "   ", steps: [] });
  assert.deepEqual(scheduleMessage(blank as never, tlDetail, false, null), []);
});
ok("timeline 里的 step id 查不到时跳过，不抛错", () => {
  const bad = message({ id: "a5", steps: [], timeline: [{ kind: "step", id: "nope" }, { kind: "text", id: "x1", text: "尾" }] });
  const blocks = scheduleMessage(bad as never, tlDetail, false, null);
  assert.deepEqual(blocks.map((b) => b.kind), ["text"]);
});
ok("孤儿助手消息单独成轮（user 为 null，不丢内容）", () => {
  const turns = scheduleTurns(detail([message({ id: "a6", content: "孤儿", thinking: "", steps: [], timeline: [{ kind: "text", id: "x2", text: "孤儿" }] })]), false, null);
  assert.equal(turns.length, 1);
  assert.equal(turns[0]!.user, null);
  assert.equal(turns[0]!.blocks.length, 1);
});
ok("两条用户消息切成两轮", () => {
  const turns = scheduleTurns(
    detail([
      { id: "u1", role: "user", content: "一", created_at: "x" },
      message({ id: "a1", content: "答一", timeline: [{ kind: "text", id: "x1", text: "答一" }] }),
      { id: "u2", role: "user", content: "二", created_at: "x" },
      message({ id: "a2", content: "答二", timeline: [{ kind: "text", id: "x2", text: "答二" }] }),
    ]),
    false,
    null,
  );
  assert.equal(turns.length, 2);
  assert.equal(turns[0]!.blocks.length, 1);
  assert.equal(turns[1]!.user?.content, "二");
  assert.equal(turns[1]!.blocks.length, 1);
});

console.log("\n[5] blocksForPhase —— 思考阶段裁掉未接替的正文");
ok("最后是 thinking 时隐藏 text", () => {
  const blocks = [
    { kind: "text", id: "t1", text: "旧", streaming: false },
    { kind: "thinking", id: "k1", text: "想", streaming: true },
  ] as never;
  assert.deepEqual(blocksForPhase(blocks, "thinking").map((b) => b.kind), ["thinking"]);
});
ok("最后是 text 时保留", () => {
  const blocks = [
    { kind: "thinking", id: "k1", text: "想", streaming: false },
    { kind: "text", id: "t1", text: "新", streaming: true },
  ] as never;
  assert.deepEqual(blocksForPhase(blocks, "thinking").map((b) => b.kind), ["thinking", "text"]);
});
ok("phase=null 时原样返回", () => {
  const blocks = [{ kind: "text", id: "t1", text: "x", streaming: false }] as never;
  assert.equal(blocksForPhase(blocks, null).length, 1);
});

console.log("\n[6] agent-output —— 工具输出解析（guards 改造后）");
ok("url 优先，回落 product_url", () => {
  const out = extractProducts({ platform: "xianyu", items: [{ item_id: "1", title: "A", url: "https://u", product_url: "https://p" }] });
  assert.equal(out[0]?.product_url, "https://u");
});
ok("只有 product_url 时用它", () => {
  const out = extractProducts({ platform: "xianyu", items: [{ item_id: "1", title: "A", product_url: "https://p" }] });
  assert.equal(out[0]?.product_url, "https://p");
});
ok("都没有则为 undefined", () => {
  const out = extractProducts({ platform: "xianyu", items: [{ item_id: "1", title: "A" }] });
  assert.equal(out[0]?.product_url, undefined);
});
ok("单 item 载荷归一成数组", () => {
  const out = extractProducts({ platform: "xianyu", item: { item_id: "2", title: "B" } });
  assert.equal(out.length, 1);
  assert.equal(out[0]?.id, "2");
});
ok("数字 id 仍被 String 转换（判定不转换）", () => {
  const out = extractProducts({ platform: "xianyu", items: [{ item_id: 7, title: "C" }] });
  assert.equal(out[0]?.id, "7");
});
ok("缺 platform 直接放弃", () => {
  assert.deepEqual(extractProducts({ items: [{ item_id: "1", title: "A" }] }), []);
});
ok("JSON 字符串载荷可解析", () => {
  const out = extractProducts(JSON.stringify({ platform: "xianyu", items: [{ item_id: "1", title: "A" }] }));
  assert.equal(out.length, 1);
});
ok("非 JSON 字符串 / null 不抛错", () => {
  assert.deepEqual(extractProducts("not json"), []);
  assert.deepEqual(extractProducts(null), []);
});
ok("seller_nick / location 走 isString", () => {
  const out = extractProducts({ platform: "xianyu", items: [{ item_id: "1", title: "A", seller_nick: "S", location: 123 }] });
  assert.equal(out[0]?.seller, "S");
  assert.equal(out[0]?.location, undefined);
});
ok("comments 逐条容错", () => {
  const out = extractProducts({
    platform: "xianyu",
    items: [{ item_id: "1", title: "A", comments: [{ content: " 好 ", author: "甲", time: "t", reply: 9 }, { content: "   " }, "垃圾"] }],
  });
  assert.equal(out[0]?.comments?.length, 1);
  assert.equal(out[0]?.comments?.[0]?.content, "好");
  assert.equal(out[0]?.comments?.[0]?.reply, null);
});
ok("比价视图解析 + queries / compare_reasons", () => {
  const v = extractComparison({
    kind: "price_compare",
    platform: "ali1688",
    source: { item_id: "s", title: "源" },
    items: [{ item_id: "1", title: "A", supplier: "S", compare_reasons: ["r1", 2], compare_score: "9", round: 1 }],
    queries: ["q1"],
    total_candidates: 5,
    rounds: 2,
  });
  assert.equal(v?.items[0]?.compare_reasons.join(","), "r1,2");
  assert.equal(v?.items[0]?.compare_score, 9);
  assert.equal(v?.queries.join(","), "q1");
  assert.equal(v?.total_candidates, 5);
});
ok("非 price_compare 形状返回 null", () => {
  assert.equal(extractComparison({ kind: "other", items: [] }), null);
  assert.equal(extractComparison({ kind: "price_compare" }), null);
});
ok("source 缺字段时用空对象兜底（不抛错）", () => {
  const v = extractComparison({ kind: "price_compare", items: [{ item_id: "1", title: "A" }] });
  assert.equal(v?.source.item_id, "");
  assert.equal(v?.source.price, null);
});
ok("source.price 空串归 null，0 归 \"0\"（textOrNull）", () => {
  const a = extractComparison({ kind: "price_compare", items: [{ item_id: "1", title: "A" }], source: { price: "" } });
  assert.equal(a?.source.price, null);
  const b = extractComparison({ kind: "price_compare", items: [{ item_id: "1", title: "A" }], source: { price: 0 } });
  assert.equal(b?.source.price, "0");
});
ok("mergeProducts 按 id 去重并打 step_id", () => {
  const cur = { items: [{ id: "p1", title: "旧", step_id: "s0" }], total: 1, status } as never;
  const merged = mergeProducts(cur, [{ id: "p1", title: "新", platform: "xianyu", price: "2", crawled_at: "t" }] as never, "s1");
  assert.equal(merged.items.length, 1);
  assert.equal(merged.items[0]?.step_id, "s1");
  assert.equal(merged.total, 1);
});
ok("mergeProducts 空数组保持原引用", () => {
  const cur = { items: [], total: 0, status } as never;
  assert.equal(mergeProducts(cur, [], "s1"), cur);
});
ok("mergeComparison 累积轮次与理由（不覆盖）", () => {
  const first = extractComparison({ kind: "price_compare", items: [{ item_id: "1", title: "A", compare_reasons: ["r1"], round: 1 }], total_candidates: 2, rounds: 1 })!;
  const second = extractComparison({ kind: "price_compare", items: [{ item_id: "1", title: "A", compare_reasons: ["r2"], round: 1 }, { item_id: "2", title: "B" }], total_candidates: 3, rounds: 1 })!;
  const merged = mergeComparison(first, second);
  const one = merged.items.find((i) => i.id === "1")!;
  assert.deepEqual(one.compare_reasons, ["r1", "r2"]);
  assert.equal(one.round, 1);
  assert.equal(merged.items.length, 2);
  assert.equal(merged.total_candidates, 5);
  assert.equal(merged.rounds, 2);
});

console.log(`\n通过 ${passed} 项${process.exitCode ? "，有失败" : "，全部通过"}\n`);
