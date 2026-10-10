import { describe, expect, it } from "vitest";
import { isPortConnectionValid, isTypeCompatible, portTypes } from "../src/validate";
import type { WorkflowNode } from "../src/types";

/** 组一个最小测试节点：只带 ports，不关心画布坐标。 */
function makeNode(id: string, ports: { id: string; kind: "source" | "target"; dataType: string | string[] }[]): WorkflowNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { ports },
  } as WorkflowNode;
}

describe("portTypes", () => {
  it("摊平数组与逗号复合类型", () => {
    expect(portTypes(["IMAGE", "MASK"])).toEqual(["IMAGE", "MASK"]);
    expect(portTypes("IMAGE, MASK")).toEqual(["IMAGE", "MASK"]);
    expect(portTypes("*")).toEqual(["*"]);
  });
});

describe("isTypeCompatible", () => {
  it("通配任意一方都放行", () => {
    expect(isTypeCompatible("*", "IMAGE")).toBe(true);
    expect(isTypeCompatible("IMAGE", "*")).toBe(true);
  });

  it("交集兼容", () => {
    expect(isTypeCompatible("IMAGE,MASK", "MASK")).toBe(true);
    expect(isTypeCompatible(["AUDIO", "VIDEO"], "VIDEO")).toBe(true);
  });

  it("无交集拒绝", () => {
    expect(isTypeCompatible("IMAGE", "AUDIO")).toBe(false);
    expect(isTypeCompatible("STRING", ["INT", "FLOAT"])).toBe(false);
  });

  it("空类型声明拒绝", () => {
    expect(isTypeCompatible("", "IMAGE")).toBe(false);
  });
});

describe("isPortConnectionValid", () => {
  const source = makeNode("a", [{ id: "out", kind: "source", dataType: "IMAGE" }]);
  const target = makeNode("b", [{ id: "in", kind: "target", dataType: ["IMAGE", "MASK"] }]);

  it("兼容连线放行", () => {
    expect(isPortConnectionValid(
      { source: "a", sourceHandle: "out", target: "b", targetHandle: "in" },
      source,
      target,
    )).toBe(true);
  });

  it("自连拒绝", () => {
    expect(isPortConnectionValid(
      { source: "a", sourceHandle: "out", target: "a", targetHandle: "out" },
      source,
      source,
    )).toBe(false);
  });

  it("端口不存在拒绝", () => {
    expect(isPortConnectionValid(
      { source: "a", sourceHandle: "missing", target: "b", targetHandle: "in" },
      source,
      target,
    )).toBe(false);
    expect(isPortConnectionValid(
      { source: "a", sourceHandle: "out", target: "b", targetHandle: "in" },
      undefined,
      target,
    )).toBe(false);
  });

  it("方向不符拒绝", () => {
    expect(isPortConnectionValid(
      { source: "a", sourceHandle: "in", target: "b", targetHandle: "out" },
      source,
      target,
    )).toBe(false);
  });

  it("类型不兼容拒绝", () => {
    const audio = makeNode("c", [{ id: "in", kind: "target", dataType: "AUDIO" }]);
    expect(isPortConnectionValid(
      { source: "a", sourceHandle: "out", target: "c", targetHandle: "in" },
      source,
      audio,
    )).toBe(false);
  });
});
