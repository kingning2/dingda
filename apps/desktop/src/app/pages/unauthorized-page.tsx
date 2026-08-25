/**
 * 401 未授权页 — 沉浸式 License 解锁流程。
 */

import { Navigate } from "react-router";
import { UnlockPage, useLicenseGateContext } from "@license";

/**
 * 未激活时的全屏解锁页；授权刷新通过后回到工作区。
 */
export function UnauthorizedPage() {
  const { gateBlocks, loading } = useLicenseGateContext();

  if (!loading && !gateBlocks) {
    return <Navigate to="/" replace />;
  }

  return <UnlockPage />;
}
