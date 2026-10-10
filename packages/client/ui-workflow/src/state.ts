/**
 * 工作流画布的受控状态。
 *
 * 职责：
 *   给调用方一份开箱即用的 nodes/edges 状态与 xyflow 要求的 change 回调。
 *
 * 设计说明：
 *   - 受控而非全托管：业务侧要读写节点数据（改状态、落库），包不拦中间层
 *   - onConnect 固定打上 type: "workflow"，保证新连线直接吃自定义边的高亮样式
 */

import { useCallback, useState, type Dispatch, type SetStateAction } from "react";
import { applyEdgeChanges, applyNodeChanges, addEdge, type Connection, type Edge, type EdgeChange, type NodeChange } from "@xyflow/react";
import type { WorkflowNode } from "./types";

export type WorkflowState = {
  nodes: WorkflowNode[];
  edges: Edge[];
  setNodes: Dispatch<SetStateAction<WorkflowNode[]>>;
  setEdges: Dispatch<SetStateAction<Edge[]>>;
  onNodesChange: (changes: NodeChange<WorkflowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
};

/** 建一份受控画布状态；initial 缺省为空画布。 */
export function useWorkflowState(initial?: { nodes?: WorkflowNode[]; edges?: Edge[] }): WorkflowState {
  const [nodes, setNodes] = useState<WorkflowNode[]>(initial?.nodes ?? []);
  const [edges, setEdges] = useState<Edge[]>(initial?.edges ?? []);

  const onNodesChange = useCallback((changes: NodeChange<WorkflowNode>[]) => {
    setNodes((current) => applyNodeChanges(changes, current));
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, type: "workflow" }, current));
  }, []);

  return { nodes, edges, setNodes, setEdges, onNodesChange, onEdgesChange, onConnect };
}
