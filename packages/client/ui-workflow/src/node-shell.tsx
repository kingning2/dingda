/**
 * 工作流节点的统一外壳。
 *
 * 职责：
 *   给所有业务节点提供同一套骨架：标题栏（图标 + 双击改名 + hover 操作 + 状态点）、
 *   内容卡片（选中高亮 / 加载态）与两侧均分的图标端口。
 *
 * 设计说明：
 *   - 必须在 ReactFlow 子树内使用（连线状态取自画布 store）；业务节点组件只填 children
 *   - 卡片最小高度随端口数联动（max(100, (maxSideCount+1)*44)），端口多时不挤压
 *   - 交互防穿透与状态色全在 workflow.css，本组件只负责结构
 */

import { useMemo, useState, type ReactNode } from "react";
import { useStore } from "@xyflow/react";
import { Loader2 } from "lucide-react";
import { cn } from "@v2/ui-primitives/utils";
import { NodePort } from "./ports";
import type { NodeStatus, PortSpec } from "./types";

export type NodeShellProps = {
  /** xyflow 节点 id：用于从画布连线里算出「哪些端口已连接」。 */
  id: string;
  /** 选中态：由节点组件从 xyflow 的 selected 透传，控制卡片高亮。 */
  selected?: boolean;
  /** 标题；双击行内改名。 */
  label?: string;
  /** 标题图标（lucide 组件），缺省不显示。 */
  icon?: ReactNode;
  /** 运行状态；idle 不渲染状态点。 */
  status?: NodeStatus;
  /** 加载中：内容区替换为加载占位。 */
  loading?: boolean;
  /** 端口声明；来自节点 data.ports。 */
  ports?: PortSpec[];
  /** 标题栏右侧操作区（刷新 / 下载 / 删除…），hover 才出现。 */
  actions?: ReactNode;
  /** 双击改名提交回调；不传则标题只读。 */
  onLabelChange?: (label: string) => void;
  /** 卡片内容 = 业务节点的主体。 */
  children: ReactNode;
};

/** 渲染节点骨架。 */
export function NodeShell({ id, selected, label, icon, status, loading, ports, actions, onLabelChange, children }: NodeShellProps) {
  const connectedPorts = useStore(
    (state) => {
      const set = new Set<string>();
      for (const edge of state.edges) {
        if (edge.source === id) set.add(`source:${edge.sourceHandle ?? ""}`);
        if (edge.target === id) set.add(`target:${edge.targetHandle ?? ""}`);
      }
      return set;
    },
    (a, b) => a.size === b.size && [...a].every((key) => b.has(key)),
  );

  const targets = useMemo(() => (ports ?? []).filter((port) => port.kind === "target"), [ports]);
  const sources = useMemo(() => (ports ?? []).filter((port) => port.kind === "source"), [ports]);
  const cardMinHeight = Math.max(100, (Math.max(targets.length, sources.length) + 1) * 44);

  return (
    <div className={cn("wf-node", selected && "wf-node--selected")}>
      <div className="wf-node__title">
        {icon}
        <TitleInput label={label} editable={!!onLabelChange} onCommit={onLabelChange} />
        {status && status !== "idle" ? <span className={`wf-node__dot wf-node__dot--${status}`} aria-label={status} /> : null}
        {actions ? <div className="wf-node__actions">{actions}</div> : null}
      </div>
      <div className={cn("wf-node__card", selected && "wf-node__card--selected", status === "error" && "wf-node__card--error")}
        style={{ minHeight: cardMinHeight }}>
        {loading ? (
          <div className="wf-node__loading" role="status">
            <Loader2 className="wf-node__spinner" size={24} aria-hidden />
            <span>加载中…</span>
          </div>
        ) : (
          children
        )}
        {targets.map((port, index) => (
          <NodePort key={port.id} port={port} index={index} count={targets.length}
            connected={connectedPorts.has(`target:${port.id}`)} />
        ))}
        {sources.map((port, index) => (
          <NodePort key={port.id} port={port} index={index} count={sources.length}
            connected={connectedPorts.has(`source:${port.id}`)} />
        ))}
      </div>
    </div>
  );
}

/** 标题：静态文本（双击进入编辑）或行内输入框；不可编辑时退化为纯文本。 */
function TitleInput({ label, editable, onCommit }: { label?: string; editable: boolean; onCommit?: (label: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  if (!editing) {
    return (
      <span
        className="wf-node__label"
        title={`${label ?? "未命名节点"}${editable ? "（双击编辑名称）" : ""}`}
        tabIndex={editable ? 0 : undefined}
        onDoubleClick={editable ? () => { setDraft(label ?? ""); setEditing(true); } : undefined}
        onKeyDown={editable ? (event) => { if (event.key === "Enter") { setDraft(label ?? ""); setEditing(true); } } : undefined}>
        {label ?? "未命名节点"}
      </span>
    );
  }
  return (
    <input
      className="wf-node__label-input"
      value={draft}
      aria-label="节点名称"
      autoFocus
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        // 中文输入法组词中的 Enter 是选字，不能当成提交。
        if (event.key === "Enter" && !event.nativeEvent.isComposing) commit();
        if (event.key === "Escape") setEditing(false);
      }}
      onBlur={commit}
      onClick={(event) => event.stopPropagation()}
      onPointerDown={(event) => event.stopPropagation()} />
  );

  function commit() {
    const value = draft.trim();
    if (value) onCommit?.(value);
    setEditing(false);
  }
}
