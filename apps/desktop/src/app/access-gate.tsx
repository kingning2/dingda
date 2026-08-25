/**
 * 工作区入口闸门 — 授权未通过走 401，后端不可用走 503。
 */

import { type ReactNode } from "react";
import { Navigate } from "react-router";
import { Loading } from "@desk/ui";
import { useLicenseGateContext } from "@license";
import { logStartupPhase, useErrorStore } from "../lifecycle";

/**
 * 拦截未授权与服务不可用，避免进入工作区壳。
 *
 * @param props.children - 已通过闸门后的工作区
 */
export function AccessGate({ children }: { children: ReactNode }) {
  const { loading, error } = useLicenseGateContext();
  const backendUnavailable = useErrorStore((state) => state.backendUnavailable);

  if (loading) {
    logStartupPhase("frontend.gate.blocking");
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loading size="lg" text="正在校验授权" />
      </div>
    );
  }

  if (backendUnavailable || error) {
    logStartupPhase("frontend.gate.redirect-503");
    return <Navigate to="/503" replace />;
  }

  logStartupPhase("frontend.gate.open");
  return children;
}
