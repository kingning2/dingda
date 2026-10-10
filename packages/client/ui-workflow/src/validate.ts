/**
 * 连线校验：类型兼容判定与连线合法性（纯函数，不依赖 React / DOM）。
 *
 * 职责：
 *   回答「这两根端口能不能连」，给 isValidConnection 与单测共用。
 *
 * 设计说明：
 *   - 校验分三层：自连拒绝 → 端口存在且方向正确 → 类型兼容；
 *     任何一层不过都返回 false，错误细节不外泄（画布反馈靠 CSS 状态色）
 *   - 逗号复合类型（"IMAGE,MASK"）与数组复合类型等价，都拆开比对
 */

import type { Node, Connection, Edge } from "@xyflow/react";
import type { PortSpec, PortType } from "./types";

/** 把单值或数组形式的类型声明摊平成集合；非字符串项直接丢弃。 */
export function portTypes(dataType: PortType | PortType[]): string[] {
  const list = Array.isArray(dataType) ? dataType : [dataType];
  return list
    .filter((item): item is string => typeof item === "string")
    .flatMap((item) => item.split(","))
    .map((item) => item.trim())
    .filter(Boolean);
}

/**
 * 判断源端口类型与目标端口类型是否兼容。
 * 任一方含 `"*"` 即放行；否则要求两侧类型列表有交集。
 */
export function isTypeCompatible(
  sourceType: PortType | PortType[],
  targetType: PortType | PortType[],
): boolean {
  const source = portTypes(sourceType);
  const target = portTypes(targetType);
  if (!source.length || !target.length) return false;
  if (source.includes("*") || target.includes("*")) return true;
  return source.some((item) => target.includes(item));
}

/**
 * 按 xyflow 的连线（Connection 或 Edge）做完整校验。
 *
 * 返回 false 的情形：自连、任一端找不到声明端口、方向不符、类型不兼容。
 * 端口表来自节点的 `data.ports`（由 NodeShell 同步），缺失时视为不可连——
 * 宁可拒绝一条合法连线，也不能放进来一条后面解析会炸的。
 */
export function isPortConnectionValid(
  connection: Connection | Edge,
  sourceNode?: Node,
  targetNode?: Node,
): boolean {
  if (!connection.source || !connection.target) return false;
  if (connection.source === connection.target) return false;

  const sourcePort = findPort(sourceNode, "source", connection.sourceHandle);
  const targetPort = findPort(targetNode, "target", connection.targetHandle);
  if (!sourcePort || !targetPort) return false;

  return isTypeCompatible(sourcePort.dataType, targetPort.dataType);
}

/** 在节点数据里找声明端口；handle 缺省时 xyflow 约定 id 为 null。 */
function findPort(node: Node | undefined, kind: PortSpec["kind"], handle?: string | null): PortSpec | undefined {
  const ports = node?.data?.ports;
  if (!Array.isArray(ports)) return undefined;
  const id = handle ?? "";
  return ports.find((port) => port && port.kind === kind && port.id === id);
}
