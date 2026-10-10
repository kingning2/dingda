/**
 * @v2/ui-workflow 出口。
 *
 * 职责：
 *   暴露应用层装配工作流画布所需的全部符号。
 *
 * 设计说明：
 *   出口数量超过「≤ 8」是出口文件的职责所在 —— 这里就是包的门面，
 *   内部文件互引一律走相对路径，不经过本文件。
 */

export { WorkflowCanvas, type WorkflowCanvasProps } from "./workflow-canvas";
export { useWorkflowState, type WorkflowState } from "./state";
export { NodeShell, type NodeShellProps } from "./node-shell";
export { NodePort, type NodePortProps } from "./ports";
export { edgeTypes } from "./edges";
export { isPortConnectionValid, isTypeCompatible, portTypes } from "./validate";
export type { NodeStatus, PortKind, PortSpec, PortType, WorkflowNode, WorkflowNodeData } from "./types";
