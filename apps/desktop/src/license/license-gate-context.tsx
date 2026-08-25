/**
 * License 闸门 React Context。
 *
 * 在 `App` 层共享 [`useLicenseGate`] 结果，避免子树重复拉取 IPC。
 *
 * @author coisini
 * @created 2026-07-16
 */

import { createContext, useContext, type ReactNode } from "react";
import type { UseLicenseGateResult } from "./use-license-gate";

const LicenseGateContext = createContext<UseLicenseGateResult | null>(null);

/**
 * Context Provider 属性。
 *
 * @author coisini
 * @created 2026-07-16
 */
export interface LicenseGateProviderProps {
  /** 闸门 Hook 返回值。 */
  value: UseLicenseGateResult;
  /** 子节点。 */
  children: ReactNode;
}

/**
 * 注入授权闸门状态。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @param props - Provider 属性
 * @returns Provider 节点
 */
export function LicenseGateProvider({ value, children }: LicenseGateProviderProps) {
  return (
    <LicenseGateContext.Provider value={value}>{children}</LicenseGateContext.Provider>
  );
}

/**
 * 读取共享的授权闸门状态。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @returns 闸门 Hook 返回值
 * @throws 未包裹 Provider 时抛出错误
 */
export function useLicenseGateContext(): UseLicenseGateResult {
  const value = useContext(LicenseGateContext);
  if (!value) {
    throw new Error("useLicenseGateContext must be used within LicenseGateProvider");
  }
  return value;
}
