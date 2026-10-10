/**
 * 画布端口（Handle）组件。
 *
 * 职责：
 *   把 xyflow 的裸 Handle 渲染成「图标端口」：未连接虚线圈、已连接实心点，
 *   并提供磁性微动效与连线状态色。
 *
 * 设计说明：
 *   - 端口图标默认 opacity 0，hover 节点 / 已连接 / 拖线中才点亮 —— 画面干净的关键
 *   - 磁性动效只在 Handle 元素上写 CSS 变量（--wf-port-x/y），不进 React 渲染
 *   - 热区由 CSS 的 ::before 扩大（inset -13px），比改 Handle 自身尺寸安全
 */

import { Handle, Position } from "@xyflow/react";
import { Circle, CircleDot } from "lucide-react";
import { cn } from "@v2/ui-primitives/utils";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { PortSpec } from "./types";

export type NodePortProps = {
  /** 端口声明（id / 方向 / 类型）。 */
  port: PortSpec;
  /** 同侧端口中的序号（从 0 起），与 count 一起决定纵向位置。 */
  index: number;
  /** 同侧端口总数；0 时该侧不渲染。 */
  count: number;
  /** 是否已有连线接入，决定实心/虚线图标。 */
  connected: boolean;
};

/**
 * 渲染一个端口。
 * 纵向位置按同侧端口数均分：top = (i+1)/(n+1)*100%，端口再多也不互相压盖。
 */
export function NodePort({ port, index, count, connected }: NodePortProps) {
  const types = port.label ?? port.id;
  const dataType = Array.isArray(port.dataType) ? port.dataType.join(" / ") : port.dataType;
  return (
    <Handle
      id={port.id}
      type={port.kind}
      position={port.kind === "source" ? Position.Right : Position.Left}
      className={cn("wf-port", connected && "wf-port--connected")}
      style={{ top: `${((index + 1) / (count + 1)) * 100}%` }}
      title={`${types} · ${dataType}`}
      aria-label={`${types} · ${dataType}`}
      onPointerMove={moveMagnet}
      onPointerLeave={resetMagnet}>
      {connected ? (
        <CircleDot className="wf-port__icon" size={18} strokeWidth={1.6} aria-hidden />
      ) : (
        <Circle className="wf-port__icon" size={18} strokeWidth={1.6} aria-hidden />
      )}
    </Handle>
  );
}

/**
 * 磁性微动效：按指针相对端口中心的偏移写 CSS 变量，图标轻轻跟手。
 * 总偏移限幅 6px（strength 递减），只做「吸附感」，不抢拖线的操作权。
 */
function moveMagnet(event: ReactPointerEvent<HTMLDivElement>) {
  if (event.pointerType === "touch") return;
  const rect = event.currentTarget.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = ((event.clientX - rect.left - rect.width / 2) / rect.width) * 18;
  const y = ((event.clientY - rect.top - rect.height / 2) / rect.height) * 18;
  const strength = Math.min(0.3, 6 / (Math.hypot(x, y) || 1));
  event.currentTarget.style.setProperty("--wf-port-x", `${x * strength}px`);
  event.currentTarget.style.setProperty("--wf-port-y", `${y * strength}px`);
}

/** 指针离开时清掉磁性偏移，图标弹回原位。 */
function resetMagnet(event: ReactPointerEvent<HTMLDivElement>) {
  event.currentTarget.style.removeProperty("--wf-port-x");
  event.currentTarget.style.removeProperty("--wf-port-y");
}
