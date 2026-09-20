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
  extractAppraisal,
  extractComparison,
  extractProducts,
  extractSelection,
  mergeComparison,
  mergeProducts,
} from "@v2/ui-ai/work/agent-output";

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

  // 【回归】2026-09-09 引入 headroom 后，工具首次做内容检测会往 stderr 打一行
  // warning；Agent 侧拿到的是 stdout+stderr 合并文本，整段不再是合法 JSON，
  // 于是抓取明明成功、结果面板却恒为 0 条。
  it("工具输出混入 stderr 日志行时仍能提取", () => {
    const noisy =
      "Content detection using pure-Python backend (native Magika/ONNX detector is unsafe " +
      "by default on Windows; override with HEADROOM_DETECT_BACKEND=rust).\n" +
      JSON.stringify({ platform: "xianyu", items: [{ item_id: "1", title: "A" }] });
    const out = extractProducts(noisy);
    expect(out).toHaveLength(1);
    expect(out[0]?.title).toBe("A");
  });

  it("日志在前后各占一行、JSON 为多行时也能提取", () => {
    const noisy = [
      "WARNING something",
      JSON.stringify({ platform: "xianyu", items: [{ item_id: "2", title: "B" }] }, null, 2),
      "done",
    ].join("\n");
    const out = extractProducts(noisy);
    expect(out).toHaveLength(1);
    expect(out[0]?.title).toBe("B");
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

describe("extractSelection", () => {
  const valid = {
    kind: "product_selection",
    platforms: ["xianyu"],
    candidates: [
      {
        keyword: "露营折叠桌",
        platform: "xianyu",
        score: 71.1,
        evidence_coverage: 1,
        sample_size: 3,
        state_known: 3,
        sold_count: 1,
        availability: "unverified",
        reasons: ["需求热度 90（同平台最高 90）", ""],
        evidence_gaps: ["售出验证：样本 1 条太少"],
        dimensions: { demand: 1, competition: 0.925, bogus: "x" },
      },
    ],
    excluded: [{ keyword: "车载收纳箱", platform: "xianyu", error_code: "channel.risk" }],
    partial: false,
    reason: "新手起步",
  };

  it("认 product_selection 载荷并带出候选与依据", () => {
    const view = must(extractSelection(valid));
    expect(view.items).toHaveLength(1);
    expect(view.items[0]?.keyword).toBe("露营折叠桌");
    expect(view.items[0]?.id).toBe("xianyu:露营折叠桌");
    expect(view.items[0]?.score).toBe(71.1);
    expect(view.items[0]?.reasons).toEqual(["需求热度 90（同平台最高 90）"]);
    expect(view.items[0]?.evidence_gaps).toHaveLength(1);
    expect(view.excluded).toHaveLength(1);
    expect(view.platforms).toEqual(["xianyu"]);
  });

  it("dimensions 只留数字，非数字的键丢掉而不是编成 0", () => {
    const view = must(extractSelection(valid));
    expect(view.items[0]?.dimensions).toEqual({ demand: 1, competition: 0.925 });
    expect("bogus" in (view.items[0]?.dimensions ?? {})).toBe(false);
  });

  it("score 缺失是 null，不是 0（0 分会被读成「量过且很差」）", () => {
    const view = must(
      extractSelection({
        kind: "product_selection",
        candidates: [{ keyword: "甲", platform: "xianyu", evidence_gaps: ["全部维度都缺证据"] }],
      }),
    );
    expect(view.items[0]?.score).toBeNull();
    expect(view.items[0]?.evidence_coverage).toBeNull();
  });

  it("缺 keyword / platform 的候选丢掉，不生成半截行", () => {
    const view = must(
      extractSelection({
        kind: "product_selection",
        candidates: [{ keyword: "甲" }, { platform: "xianyu" }, { keyword: "乙", platform: "xianyu" }],
      }),
    );
    expect(view.items.map((item) => item.keyword)).toEqual(["乙"]);
  });

  it("非 product_selection 形状返回 null", () => {
    expect(extractSelection({ kind: "price_compare", candidates: [] })).toBeNull();
    expect(extractSelection({ kind: "product_selection" })).toBeNull();
    expect(extractSelection(null)).toBeNull();
  });

  it("空候选时 status 掉到 error，且带上工具的 message", () => {
    const view = must(
      extractSelection({
        kind: "product_selection",
        candidates: [],
        message: "闲鱼：候选都没取到可用样本",
      }),
    );
    expect(view.status.state).toBe("error");
    expect(view.status.hint).toContain("没取到可用样本");
  });

  it("partial 结果在 status.label 上标出来", () => {
    const view = must(extractSelection({ ...valid, partial: true }));
    expect(view.status.label).toContain("不完整");
  });

  it("【回归】选品载荷不会被 extractProducts 吞掉", () => {
    // 选品出参故意不带顶层 platform + items —— 带上就会被 extractProducts 认领，
    // 候选表会被当成商品列表塞进商品面板。
    const output = {
      kind: "product_selection",
      platforms: ["xianyu"],
      candidates: [
        {
          keyword: "甲",
          platform: "xianyu",
          sample_size: 3,
          score: 60,
          // 故意混进一个看起来像商品的键，确认它不会被当成商品行
          title: "货",
          item_id: "x1",
        },
      ],
    };
    expect(extractProducts(output)).toEqual([]);
    expect(extractSelection(output)?.items).toHaveLength(1);
  });
});

describe("extractAppraisal", () => {
  const valid = {
    kind: "product_appraisal",
    query: "露营折叠桌",
    score: 87,
    verdict: "worth",
    verdict_label: "值得买",
    verdict_reason: "比同款中位价低 80%，需求也量到了，有转卖空间",
    evidence_coverage: 1,
    dimensions: { margin: 1, demand: 1, competition: 0.85, bogus: "x" },
    reasons: ["价差空间 同款中位价 ¥50，本商品 ¥10（低 80%）", ""],
    evidence_gaps: ["售出验证：该平台不产出售出状态，这项无法量"],
    target: { item_id: "t", title: "本商品", price: "10", platform: "xianyu", is_target: true, price_delta_pct: 0 },
    comparables: [
      { item_id: "t", title: "本商品", price: "10", platform: "xianyu", is_target: true, price_delta_pct: 0 },
      { item_id: "a", title: "同款甲", price: "40", platform: "xianyu", seller_nick: "甲", want_count: "5", sold_state: "on_sale", is_target: false, price_delta_pct: 300 },
    ],
    spread: 0.8,
    price_p25: 40,
    price_median: 50,
    price_p75: 60,
    sample_size: 1,
    partial: false,
  };

  it("认 product_appraisal 载荷并带出判词与同款表", () => {
    const view = must(extractAppraisal(valid));
    expect(view.verdict).toBe("worth");
    expect(view.verdict_label).toBe("值得买");
    expect(view.score).toBe(87);
    expect(view.query).toBe("露营折叠桌");
    expect(view.target?.id).toBe("t");
    expect(view.comparables).toHaveLength(2);
    expect(view.comparables[1]?.seller).toBe("甲");
    expect(view.comparables[1]?.price_delta_pct).toBe(300);
    expect(view.status.state).toBe("ready");
  });

  it("dimensions 只留数字，非数字的键丢掉而不是编成 0", () => {
    const view = must(extractAppraisal(valid));
    expect(view.dimensions).toEqual({ margin: 1, demand: 1, competition: 0.85 });
  });

  it("score 缺失是 null，不是 0（0 分会被读成「量过且很差」）", () => {
    const view = must(
      extractAppraisal({
        kind: "product_appraisal",
        verdict: "insufficient",
        verdict_label: "判不了",
        target: { item_id: "t", title: "本商品" },
        comparables: [],
      }),
    );
    expect(view.score).toBeNull();
    expect(view.spread).toBeNull();
    expect(view.status.state).toBe("ready");
  });

  it("同款行缺 item_id / title 的丢掉，不生成半截行", () => {
    const view = must(
      extractAppraisal({
        ...valid,
        comparables: [{ item_id: "a" }, { title: "无 id" }, { item_id: "b", title: "  " }, { item_id: "c", title: "好" }],
      }),
    );
    expect(view.comparables.map((row) => row.id)).toEqual(["c"]);
  });

  it("非 product_appraisal 形状返回 null", () => {
    expect(extractAppraisal({ kind: "product_selection", comparables: [] })).toBeNull();
    expect(extractAppraisal({ kind: "price_compare", comparables: [] })).toBeNull();
    expect(extractAppraisal(null)).toBeNull();
  });

  it("只有 kind 没有判词时也认（工具失败时带的就是这个形状），落成 error 视图", () => {
    const view = must(extractAppraisal({ kind: "product_appraisal" }));
    expect(view.status.state).toBe("error");
    expect(view.target).toBeNull();
  });

  it("本商品详情没拉到（target 为 null）时掉到 error 并带上 message", () => {
    const view = must(
      extractAppraisal({
        kind: "product_appraisal",
        target: null,
        comparables: [],
        error_code: "channel.risk",
        message: "闲鱼：拿不到本商品详情",
      }),
    );
    expect(view.target).toBeNull();
    expect(view.status.state).toBe("error");
    expect(view.status.hint).toContain("拿不到本商品详情");
  });

  it("partial 结果在 status.label 上标出来", () => {
    const view = must(extractAppraisal({ ...valid, partial: true }));
    expect(view.status.label).toContain("不完整");
  });

  it("【回归】鉴定载荷不会被 extractProducts 吞掉", () => {
    // 鉴定出参故意不带顶层 platform + items —— 带上就会被 extractProducts 认领，
    // 同款表会被当成商品列表塞进商品面板。
    const output = {
      kind: "product_appraisal",
      verdict: "worth",
      verdict_label: "值得买",
      target: { item_id: "t", title: "本商品", price: "10" },
      comparables: [{ item_id: "a", title: "同款甲", price: "40" }],
    };
    expect(extractProducts(output)).toEqual([]);
    expect(extractAppraisal(output)?.comparables).toHaveLength(1);
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

  it("并同一轮不是幂等的：候选数与轮次会翻倍", () => {
    // 冷接回是「从 0 整轮重放」，所以第一段重放的比价必须**替换**而不是并上去
    // （见 `work/send.ts` 的 replaceComparisonFirst）。这条钉住那个理由。
    const round = must(
      extractComparison({
        kind: "price_compare",
        items: [{ item_id: "1", title: "A" }],
        total_candidates: 2,
        rounds: 1,
      }),
    );

    const twice = mergeComparison(mergeComparison(null, round), round);
    expect(twice.items).toHaveLength(1);
    expect(twice.total_candidates).toBe(4);
    expect(twice.rounds).toBe(2);
  });
});
