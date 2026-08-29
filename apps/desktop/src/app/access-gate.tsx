/**
 * 工作区入口闸门 — 授权校验中拦截进入；错误态由工作区内联展示。
 */

import { type ReactNode } from "react";
import { Loading } from "@desk/ui";
import { useLicenseGateContext } from "@license";
import { logStartupPhase } from "../lifecycle";

/**
 * 授权校验未完成前不进入工作区；后端不可用与授权错误保持壳挂载，
 * 由 WorkspaceOutlet 在内容区渲染 503，避免全屏覆盖侧栏。
 *
 * @param props.children - 已通过闸门后的工作区
 */
export function AccessGate({ children }: { children: ReactNode }) {
  const { loading } = useLicenseGateContext();

  if (loading) {
    logStartupPhase("frontend.gate.blocking");
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loading size="lg" text="正在校验授权" />
      </div>
    );
  }

  logStartupPhase("frontend.gate.open");
  return children;
}
