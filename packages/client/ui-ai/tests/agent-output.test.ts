/**
 * 工具输出解析测试。
 *
 * 工具输出是外部 CLI 给的，形状不保证，所以这里测的全是**容错路径**：
 * 字段缺失、类型不对、载荷有两种形状、JSON 字符串 vs 对象。
 *
 * 回归重点（曾出过真 bug）：`items` 是数组时必须取到它本身。
 * 判定器曾因「数组即候选列表」的语义颠倒去数组**里面**找数组，返回兜底空数组，
 * 导致商品 / 比价 / comments 全部静默清空 —— 不报错，只是内容没了。
 */
import { describe, expect, it } from "vitest";

import {
  extractComparison,
  extractProducts,
  mergeComparison,
  mergeProducts,
} from "@v2/ui-ai/agent-output";

const status = { state: "ready", label: "已完成", hint: null, badge_class: "b" };

/** 断言解析成功 —— 比在每处写 `!` 更能说明「这里必须解析出结果」。 */
function must<T>(value: T | null): T {
  if (value === null) throw new Error("期望解析出结果，实际是 null");
  return value;
}

describe("extractProducts", () => {
  it("【回归】items 数组载荷能取到商品（数组字段不能被当成候选列表）", () => {
    const out = extractProducts({
      platform: "xianyu",
      items: [{ item_id: "1", title: "A" }],
    });
    expect(out).toHaveLength(1);
    expect(out[0]?.id).toBe("1");
  });

  it("单 item 载荷归一成数组", () => {
    const out = extractProducts({ platform: "xianyu", item: { item_id: "2", title: "B" } });
    expect(out).toHaveLength(1);
    expect(out[0]?.id).toBe("2");
  });

  it("url 优先，回落 product_url，都没有则 undefined", () => {
    const both = extractProducts({
      platform: "xianyu",
      items: [{ item_id: "1", title: "A", url: "https://u", product_url: "https://p" }],
    });
    expect(both[0]?.product_url).toBe("https://u");

    const onlyFallback = extractProducts({
      platform: "xianyu",
      items: [{ item_id: "1", title: "A", product_url: "https://p" }],
    });
    expect(onlyFallback[0]?.product_url).toBe("https://p");

    const none = extractProducts({ platform: "xianyu", items: [{ item_id: "1", title: "A" }] });
    expect(none[0]?.product_url).toBeUndefined();
  });

  it("数字 id 仍被 String 转换（判定不转换）", () => {
    const out = extractProducts({ platform: "xianyu", items: [{ item_id: 7, title: "C" }] });
    expect(out[0]?.id).toBe("7");
  });

  it("缺 platform 直接放弃 —— 猜平台会把别处的商品混进来", () => {
    expect(extractProducts({ items: [{ item_id: "1", title: "A" }] })).toEqual([]);
  });

  it("JSON 字符串载荷可解析", () => {
    const out = extractProducts(
      JSON.stringify({ platform: "xianyu", items: [{ item_id: "1", title: "A" }] }),
    );
    expect(out).toHaveLength(1);
  });

  it("非 JSON 字符串 / null / 数组不抛错", () => {
    expect(extractProducts("not json")).toEqual([]);
    expect(extractProducts(null)).toEqual([]);
    expect(extractProducts([])).toEqual([]);
  });

  it("id 或标题缺失的条目被丢掉（渲染出来是点不开的空壳）", () => {
    const out = extractProducts({
      platform: "xianyu",
      items: [{ item_id: "1" }, { title: "无 id" }, { item_id: "2", title: "  " }, { item_id: "3", title: "好" }],
    });
    expect(out.map((i) => i.id)).toEqual(["3"]);
  });

  it("字符串字段走 isString：类型不对则为 undefined", () => {
    const out = extractProducts({
      platform: "xianyu",
      items: [{ item_id: "1", title: "A", seller_nick: "S", location: 123 }],
    });
    expect(out[0]?.seller).toBe("S");
    expect(out[0]?.location).toBeUndefined();
  });

  it("comments 逐条容错，空白内容丢掉", () => {
    const out = extractProducts({
      platform: "xianyu",
      items: [
        {
          item_id: "1",
          title: "A",
          comments: [
            { content: " 好 ", author: "甲", time: "t", reply: 9 },
            { content: "   " },
            "垃圾",
          ],
        },
      ],
    });
    expect(out[0]?.comments).toHaveLength(1);
    expect(out[0]?.comments?.[0]?.content).toBe("好");
    expect(out[0]?.comments?.[0]?.author).toBe("甲");
    expect(out[0]?.comments?.[0]?.reply).toBeNull();
  });
});

describe("extractComparison", () => {
  const valid = {
    kind: "price_compare",
    platform: "ali1688",
    source: { item_id: "s", title: "源" },
    items: [{ item_id: "1", title: "A", supplier: "S", compare_reasons: ["r1", 2], compare_score: "9", round: 1 }],
    queries: ["q1"],
    total_candidates: 5,
    rounds: 2,
  };

  it("【回归】items 数组载荷能取到候选", () => {
    const view = extractComparison(valid);
    expect(view?.items).toHaveLength(1);
  });

  it("数值字段走 asNumber 转换，理由列表过滤空值", () => {
    const view = extractComparison(valid);
    expect(view?.items[0]?.compare_score).toBe(9);
    expect(view?.items[0]?.compare_reasons).toEqual(["r1", "2"]);
  });

  it("queries 走 isArray，取到的是数组本身", () => {
    expect(extractComparison(valid)?.queries).toEqual(["q1"]);
  });

  it("非 price_compare 形状返回 null", () => {
    expect(extractComparison({ kind: "other", items: [] })).toBeNull();
    expect(extractComparison({ kind: "price_compare" })).toBeNull();
    expect(extractComparison(null)).toBeNull();
  });

  it("source 缺字段时用空对象兜底，不抛错", () => {
    const view = extractComparison({ kind: "price_compare", items: [{ item_id: "1", title: "A" }] });
    expect(view?.source.item_id).toBe("");
    expect(view?.source.price).toBeNull();
  });

  it("source.price 空串归 null，0 归 \"0\"", () => {
    const empty = extractComparison({ kind: "price_compare", items: [], source: { price: "" } });
    expect(empty?.source.price).toBeNull();

    const zero = extractComparison({ kind: "price_compare", items: [], source: { price: 0 } });
    expect(zero?.source.price).toBe("0");
  });
});

describe("mergeProducts", () => {
  it("按 id 去重并打上来源步骤", () => {
    const current = { items: [{ id: "p1", title: "旧", step_id: "s0" }], total: 1, status } as never;
    const merged = mergeProducts(
      current,
      [{ id: "p1", title: "新", platform: "xianyu", price: "2", crawled_at: "t" }] as never,
      "s1",
    );
    expect(merged.items).toHaveLength(1);
    expect(merged.items[0]?.step_id).toBe("s1");
    expect(merged.total).toBe(1);
  });

  it("空数组保持原引用（调用方据此跳过无意义的状态更新）", () => {
    const current = { items: [], total: 0, status } as never;
    expect(mergeProducts(current, [], "s1")).toBe(current);
  });
});

describe("mergeComparison", () => {
  it("按 item_id 累积：轮次保留最早、理由取并集、候选数相加", () => {
    const first = extractComparison({
      kind: "price_compare",
      items: [{ item_id: "1", title: "A", compare_reasons: ["r1"], round: 1 }],
      total_candidates: 2,
      rounds: 1,
    });
    const second = extractComparison({
      kind: "price_compare",
      items: [
        { item_id: "1", title: "A", compare_reasons: ["r2"], round: 1 },
        { item_id: "2", title: "B" },
      ],
      total_candidates: 3,
      rounds: 1,
    });

    const merged = mergeComparison(must(first), must(second));
    const one = merged.items.find((i) => i.id === "1");
    expect(one?.compare_reasons).toEqual(["r1", "r2"]);
    expect(one?.round).toBe(1);
    expect(merged.items).toHaveLength(2);
    expect(merged.total_candidates).toBe(5);
    expect(merged.rounds).toBe(2);
  });

  it("本轮没给源商品信息时沿用上一轮的（否则右侧对比源会变空）", () => {
    const first = extractComparison({
      kind: "price_compare",
      items: [],
      source: { item_id: "s", title: "源", image_url: "i.png" },
    });
    const second = extractComparison({ kind: "price_compare", items: [], source: {} });
    expect(mergeComparison(must(first), must(second)).source.title).toBe("源");
  });

  it("current 为空时直接返回 next", () => {
    const next = extractComparison({ kind: "price_compare", items: [] });
    expect(mergeComparison(null, must(next))).toBe(next);
  });
});
