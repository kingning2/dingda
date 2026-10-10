/**
 * 工作流画布装配。
 *
 * 职责：
 *   把 ReactFlow 和本域的交互取向装成一个组件：网格对齐、克制缩放、端口类型校验、
 *   自定义边默认值，调用方只传状态与 nodeTypes。
 *
 * 设计说明：
 *   - 交互取向照搬 Toonflow 的「压默认」：滚轮不缩放（panOnScroll 平移）、
 *     双击不缩放、Delete 键不删节点 —— 误操作是画布产品最大的丑
 *   - snapGrid 与 Background 的 gap 同为 16，点阵即吸附网格
 *   - nodeTypes 必须稳定引用（模块级或 useMemo），否则 xyflow 每帧重建节点
 */

import { useMemo } from "react";
import {
  Background,
  ConnectionMode,
  PanOnScrollMode,
  ReactFlow,
  type Connection,
  type DefaultEdgeOptions,
  type Edge,
  type EdgeChange,
  type IsValidConnection,
  type NodeChange,
  type NodeTypes,
} from "@xyflow/react";
import { cn } from "@v2/ui-primitives/utils";
import { edgeTypes } from "./edges";
import { isPortConnectionValid } from "./validate";
import type { WorkflowNode } from "./types";
import "./workflow.css";

export type WorkflowCanvasProps = {
  nodes: WorkflowNode[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange<WorkflowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  /** 业务节点注册表；引用必须稳定（模块级常量或 useMemo）。 */
  nodeTypes: NodeTypes;
  className?: string;
  /** 追加在画布内的覆盖层（MiniMap / Controls / 浮动面板等）。 */
  children?: React.ReactNode;
};

/** 所有新边的默认值：走自定义边 + 40px 热区。 */
const DEFAULT_EDGE_OPTIONS: DefaultEdgeOptions = { type: "workflow", interactionWidth: 40 };

/** 渲染装配好的画布。 */
export function WorkflowCanvas({ nodes, edges, onNodesChange, onEdgesChange, onConnect, nodeTypes, className, children }: WorkflowCanvasProps) {
  const isValidConnection = useMemo<IsValidConnection>(
    () => (connection) => {
      const source = nodes.find((node) => node.id === connection.source);
      const target = nodes.find((node) => node.id === connection.target);
      return isPortConnectionValid(connection, source, target);
    },
    [nodes],
  );

  return (
    <ReactFlow
      className={cn("wf-canvas", className)}
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
      isValidConnection={isValidConnection}
      connectionMode={ConnectionMode.Strict}
      snapToGrid
      snapGrid={[16, 16]}
      minZoom={0.2}
      maxZoom={8}
      zoomOnScroll={false}
      zoomOnPinch
      zoomOnDoubleClick={false}
      panOnScroll
      panOnScrollMode={PanOnScrollMode.Free}
      deleteKeyCode={null}
      elevateNodesOnSelect
      fitView>
      <Background gap={16} color="var(--border)" />
      {children}
    </ReactFlow>
  );
}
