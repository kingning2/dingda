/**
 * 判定器行为测试。
 *
 * 重点在两处容易写错的地方：**数组的判定顺序**（先整体再逐元素）与
 * **判定不转换**（`isNumber("12")` 是 false）。这两条一旦反过来，
 * 出错形态是静默拿到兜底值，而不是报错。
 */
import { describe, expect, it } from "vitest";

import { isArray, isBoolean, isFunction, isNumber, isObject, isString } from "@v2/runtime/guards";

describe("单值与兜底", () => {
  it("命中时返回原值", () => {
    expect(isString("a", "")).toBe("a");
  });

  it("不命中时返回兜底值", () => {
    expect(isString(123, "")).toBe("");
  });

  it("兜底值决定返回类型（undefined 不特殊化）", () => {
    expect(isString(1, undefined)).toBeUndefined();
    expect(isString("a", null)).toBe("a");
  });

  it("判定不转换：数字字符串不是 number", () => {
    expect(isNumber("12", null)).toBeNull();
  });
});

describe("多候选：按顺序取第一个满足判定的", () => {
  it("跳过 null 与 undefined，取到后面的字符串", () => {
    expect(isString([undefined, null, "b", "c"], "")).toBe("b");
  });

  it("全不命中时走兜底", () => {
    expect(isString([1, 2], "z")).toBe("z");
  });

  it("空候选列表走兜底", () => {
    expect(isString([], "z")).toBe("z");
  });
});

describe("数组：先整体、再逐元素", () => {
  it("整体就是数组时直接返回它（取数组字段的常见写法）", () => {
    expect(isArray([1, 2], [])).toEqual([1, 2]);
    expect(isArray([], [])).toEqual([]);
  });

  it("顺序颠倒会静默拿到兜底 —— 这正是要防的", () => {
    // 若先逐元素，这里会去 [1,2] 里面找数组，返回兜底 []
    expect(isArray([1, 2], ["兜底"])).toHaveLength(2);
  });

  it("整体不是数组时当候选列表", () => {
    expect(isObject([{ a: 1 }], null)).toEqual({ a: 1 });
    expect(isString([1, "b"], "")).toBe("b");
  });
});

describe("各判定器的边界", () => {
  it("isNumber 拒掉 NaN 与 ±Infinity（它们 typeof 是 number）", () => {
    expect(isNumber(Number.NaN, null)).toBeNull();
    expect(isNumber(Number.POSITIVE_INFINITY, null)).toBeNull();
    expect(isNumber(Number.NEGATIVE_INFINITY, null)).toBeNull();
  });

  it("isNumber 收 0（不能靠真值判断）", () => {
    expect(isNumber(0, null)).toBe(0);
  });

  it("isObject 排除 null 与数组", () => {
    expect(isObject(null, null)).toBeNull();
    expect(isObject([], null)).toBeNull();
    expect(isObject({ a: 1 }, null)).toEqual({ a: 1 });
  });

  it("isBoolean / isFunction", () => {
    expect(isBoolean(true, false)).toBe(true);
    expect(isBoolean("true", false)).toBe(false);
    const fn = () => 1;
    expect(isFunction(fn, null)).toBe(fn);
    expect(isFunction({}, null)).toBeNull();
  });
});
