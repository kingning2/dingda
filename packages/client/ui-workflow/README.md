# @v2/ui-workflow

工作流画布域：把 `@xyflow/react` 装配成叮答的节点画布。封装取向照搬 Toonflow 的画布四层 ——
好看做成默认值、交互克制、默认隐藏状态才点亮、视觉全部走设计令牌。

## 使用

```tsx
import { NodeShell, WorkflowCanvas, useWorkflowState } from "@v2/ui-workflow";
import type { NodeTypes } from "@xyflow/react";

// 业务节点：只填外壳内容与端口声明
function SearchNode({ id, data, selected }: NodeProps) {
  return (
    <NodeShell id={id} selected={selected} label={data.label} ports={data.ports}
      icon={<Globe size={14} />} onLabelChange={...}>
      <div>搜索参数表单</div>
    </NodeShell>
  );
}

const nodeTypes: NodeTypes = { search: SearchNode }; // 引用必须稳定（模块级或 useMemo）
```

页面装配：

```tsx
const state = useWorkflowState();
<WorkflowCanvas {...state} nodeTypes={nodeTypes} />;
```

## 文件

- `src/types.ts` — 端口类型协议（`PortType`/`NodePort`/`WorkflowNodeData`）。调用方与 `validate.ts` 共用。
- `src/validate.ts` — 连线校验纯函数（`isTypeCompatible`/`isPortConnectionValid`），画布 `isValidConnection` 与单测共用。
- `src/state.ts` — 受控画布状态 `useWorkflowState`，内置 xyflow change 回调与新边类型注入。
- `src/ports.tsx` — 端口组件 `NodePort`：图标 Handle、磁性微动效、热区扩大。
- `src/node-shell.tsx` — 节点统一外壳 `NodeShell`：标题栏 / 双击改名 / 状态点 / 卡片 / 端口装配。
- `src/edges.tsx` — 自定义贝塞尔边 `WorkflowEdge`（选中 / 拖动点亮）与 `edgeTypes`。
- `src/workflow-canvas.tsx` — 画布装配 `WorkflowCanvas`：网格对齐、克制缩放、端口校验接线。
- `src/workflow.css` — 全部视觉；只用 `@v2/ui-theme` 令牌，随深色模式自动切换。
- `tests/validate.test.ts` — 校验纯函数的单测。

## 约定

- 节点端口声明放在 `data.ports`（`PortSpec[]`），方向由 `kind` 决定，同侧按序均分。
- 业务节点的 `nodeTypes` 由调用方注册；本包不内置任何叮答业务节点。
- `NodeShell` 必须在画布子树内使用（连线状态取自画布 store）。
