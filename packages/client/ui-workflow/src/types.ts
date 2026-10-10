/**
 * 工作流画布的端口类型协议。
 *
 * 职责：
 *   定义节点端口（Handle）与节点数据的形状，让「什么能连什么」由数据描述而不是散在组件里。
 *
 * 设计说明：
 *   - 类型集合先照采 ComfyUI 的常用模态裁剪（文本/图像/音频/视频/数值），不够时再加；
 *     `"*"` 表示通配，复合类型用数组表达，解析在 validate.ts
 *   - WorkflowNodeData 带索引签名是 @xyflow/react 的 Node 泛型约束（T extends Record<string, unknown>）
 */

/** 端口方向：source 是输出（右缘），target 是输入（左缘）。 */
export type PortKind = "source" | "target";

/**
 * 端口数据类型。
 * 新增类型时只改这里的字面量联合，校验逻辑在 `validate.ts` 不用动。
 */
export type PortType =
  | "STRING"
  | "INT"
  | "FLOAT"
  | "BOOLEAN"
  | "IMAGE"
  | "AUDIO"
  | "VIDEO"
  | "*"
  | (string & {});

/** 一个端口的声明 = 画布上的一个 Handle。id 在节点内唯一，方向由 kind 决定。 */
export type PortSpec = {
  id: string;
  kind: PortKind;
  dataType: PortType | PortType[];
  label?: string;
};

/** 节点运行状态，由调用方（业务节点）驱动；idle 不渲染任何标记。 */
export type NodeStatus = "idle" | "running" | "done" | "error";

/** 业务节点挂在 xyflow Node.data 上的数据形状。 */
export type WorkflowNodeData = {
  label?: string;
  ports?: PortSpec[];
  status?: NodeStatus;
  [key: string]: unknown;
};

/** 画布节点的完整类型（xyflow Node + 本域数据）。 */
export type WorkflowNode = import("@xyflow/react").Node<WorkflowNodeData>;
