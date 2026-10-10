/**
 * 工作流连线：带活动高亮的贝塞尔边。
 *
 * 职责：
 *   提供默认边类型 workflow —— 平时低调灰线，选中或拖动任一端时点亮为主题色。
 *
 * 设计说明：
 *   - 活动判定读 sourceNode/targetNode 的 dragging，比在画布层算 class 稳（xyflow 保证字段最新）
 *   - interactionWidth 40 让细线上也有宽热区，点选 / 右键断开不考验手感
 */

import { cn } from "@v2/ui-primitives/utils";
import { useInternalNode } from "@xyflow/react";

import { BaseEdge, getBezierPath, type EdgeProps, type EdgeTypes } from "@xyflow/react";

/** 自定义贝塞尔边。通过 edgeTypes 注册，key 固定为 "workflow"。 */
export function WorkflowEdge({ id, source, target, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, selected }: EdgeProps) {
  const [path] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  // EdgeProps 不带两端节点，拖动状态从内部 store 取（拖动中 useInternalNode 的 dragging 为 true）。
  const dragging = useInternalNode(source ?? "")?.dragging || useInternalNode(target ?? "")?.dragging;
  const active = !!selected || !!dragging;
  return <BaseEdge id={id} path={path} interactionWidth={40} className={cn("wf-edge", active && "wf-edge--active")} />;
}

/** 传给 ReactFlow 的 edgeTypes；模块级常量，避免每次渲染生成新引用触发重建。 */
export const edgeTypes: EdgeTypes = { workflow: WorkflowEdge };
