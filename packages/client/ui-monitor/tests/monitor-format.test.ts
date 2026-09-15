/**
 * 监控展示口径测试。
 *
 * 这里测的全是**容错与边界**：后端字段是自由字符串，值域会随 Python 侧演进。
 * 前端一旦在未知值上「猜一个」，界面上就会静默出现错误文案 ——
 * 这类问题 `tsc` 与依赖检查都看不见。
 */
import { describe, expect, it } from "vitest";

import {
  changeKindView,
  formatDrop,
  formatInterval,
  formatPrice,
  formatRelativeTime,
  monitorStateLabel,
  soldStateView,
} from "@v2/ui-monitor/monitor-format";
import { normalizeItemId } from "@v2/ui-monitor/monitor-item-id";
import { platformLabel } from "@v2/ui-monitor/monitor-platforms";

describe("soldStateView", () => {
  it("已知售出态给中文文案", () => {
    expect(soldStateView("on_sale").label).toBe("在卖");
    expect(soldStateView("sold").label).toBe("已售出");
    expect(soldStateView("gone").label).toBe("详情取不到");
  });

  it("未收录的值原样回显，不吞成「未知」", () => {
    expect(soldStateView("reserved").label).toBe("reserved");
  });

  it("空串回落「待确认」", () => {
    expect(soldStateView("").label).toBe("待确认");
  });
});

describe("changeKindView", () => {
  it("已知类型给中文文案", () => {
    expect(changeKindView("price_drop").label).toBe("降价");
    expect(changeKindView("relisted").label).toBe("重新上架");
  });

  it("未收录的类型原样回显", () => {
    expect(changeKindView("weird").label).toBe("weird");
  });
});

describe("monitorStateLabel", () => {
  it("已知状态给中文", () => {
    expect(monitorStateLabel("active")).toBe("监控中");
    expect(monitorStateLabel("paused")).toBe("已暂停");
  });

  it("未收录的状态原样回显", () => {
    expect(monitorStateLabel("frozen")).toBe("frozen");
  });
});

describe("formatPrice", () => {
  it("保留两位小数", () => {
    expect(formatPrice(12.5)).toBe("¥12.50");
    expect(formatPrice(0)).toBe("¥0.00");
  });

  it("无价格给破折号（空串会让列表看起来像加载失败）", () => {
    expect(formatPrice(null)).toBe("—");
    expect(formatPrice(Number.NaN)).toBe("—");
  });
});

describe("formatDrop", () => {
  it("正数按「已降价」口径给向下箭头", () => {
    expect(formatDrop({ price_drop: 12, price_drop_ratio: -0.08 })).toBe("↓ ¥12.00（8.0%）");
  });

  it("负数给向上箭头（后端口径：负数是涨价）", () => {
    expect(formatDrop({ price_drop: -5, price_drop_ratio: 0.05 })).toBe("↑ ¥5.00（5.0%）");
  });

  it("缺 ratio 时只给金额", () => {
    expect(formatDrop({ price_drop: 3, price_drop_ratio: null })).toBe("↓ ¥3.00");
  });

  it("没变化或没有价格给破折号", () => {
    expect(formatDrop({ price_drop: 0, price_drop_ratio: 0 })).toBe("—");
    expect(formatDrop({ price_drop: null, price_drop_ratio: null })).toBe("—");
  });
});

describe("formatInterval", () => {
  it("小于一小时按分钟", () => {
    expect(formatInterval(120)).toBe("2 分钟");
    expect(formatInterval(1800)).toBe("30 分钟");
  });

  it("整小时不带小数尾巴", () => {
    expect(formatInterval(21_600)).toBe("6 小时");
  });

  it("非整小时保留一位小数", () => {
    expect(formatInterval(5400)).toBe("1.5 小时");
  });

  it("整天的粒度切换", () => {
    expect(formatInterval(86_400)).toBe("1 天");
    expect(formatInterval(172_800)).toBe("2 天");
  });

  it("非正数给破折号", () => {
    expect(formatInterval(0)).toBe("—");
    expect(formatInterval(-1)).toBe("—");
  });
});

describe("formatRelativeTime", () => {
  /** Unix 秒，与后端 `time.time()` 同单位。 */
  const now = 1_700_000_000;

  it("一分钟内给「刚刚」", () => {
    expect(formatRelativeTime(now - 30, now)).toBe("刚刚");
  });

  it("过去时间给「前」", () => {
    expect(formatRelativeTime(now - 300, now)).toBe("5 分钟前");
    expect(formatRelativeTime(now - 7_200, now)).toBe("2 小时前");
    expect(formatRelativeTime(now - 172_800, now)).toBe("2 天前");
  });

  it("未来时间给「后」而不是负数（「-3 分钟前」读起来像 bug）", () => {
    expect(formatRelativeTime(now + 180, now)).toBe("3 分钟后");
  });

  it("【回归】参数是秒不是毫秒（毫秒会让「3 分钟」显示成「2 天」）", () => {
    expect(formatRelativeTime(now - 180, now)).toBe("3 分钟前");
  });

  it("没有时间戳给破折号", () => {
    expect(formatRelativeTime(0, now)).toBe("—");
  });
});

describe("platformLabel", () => {
  it("已知平台给中文名", () => {
    expect(platformLabel("xianyu")).toBe("闲鱼");
  });

  it("未收录的平台原样回显", () => {
    expect(platformLabel("pdd")).toBe("pdd");
  });
});

describe("normalizeItemId", () => {
  it("纯 ID 原样返回", () => {
    expect(normalizeItemId("8123456789")).toBe("8123456789");
  });

  it("从 ?id= 链接里取 ID", () => {
    expect(normalizeItemId("https://www.goofish.com/item?id=8123456789&spm=a1")).toBe("8123456789");
  });

  it("从 /item/ 路径里取 ID", () => {
    expect(normalizeItemId("https://www.goofish.com/item/8123456789")).toBe("8123456789");
  });

  it("去空白", () => {
    expect(normalizeItemId("  8123456789  ")).toBe("8123456789");
  });

  it("空输入给空串（调用方据此禁用提交）", () => {
    expect(normalizeItemId("")).toBe("");
    expect(normalizeItemId("   ")).toBe("");
  });

  it("认不出的输入原样返回，交给后端判错", () => {
    expect(normalizeItemId("https://example.com/something")).toBe("https://example.com/something");
  });
});
