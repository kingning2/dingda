/**
 * License 闸门 React Hook（薄适配层）。
 *
 * 将 [`LicenseGateController`] 接到组件状态；校验失败时用 toast 提示。
 *
 * @author coisini
 * @created 2026-07-16
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "@desk/ui";
import { LicenseGateController } from "./license-gate-controller";
import type { LicenseStatus } from "@desk/platform/ipc/license";
import { logStartupPhase } from "../lifecycle/startup-log";

/** 后台异步刷新授权状态间隔（10 分钟）。 */
const LICENSE_REFRESH_MS = 10 * 60 * 1000;

/**
 * Hook 返回值：闸门加载态与刷新入口。
 *
 * @author coisini
 * @created 2026-07-16
 */
export interface UseLicenseGateResult {
  /** 最新授权状态。 */
  status: LicenseStatus | null;
  /** 是否正在拉取。 */
  loading: boolean;
  /** 拉取失败时的错误消息。 */
  error: string | null;
  /** 是否未激活（有锁且未激活）。 */
  gateBlocks: boolean;
  /** 重新拉取状态。 */
  refresh: () => void;
}

/**
 * 订阅授权闸门状态。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @returns 闸门 UI 所需状态与 refresh
 */
export function useLicenseGate(): UseLicenseGateResult {
  const [controller] = useState(() => new LicenseGateController());
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gateBlocks, setGateBlocks] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const didNotifyError = useRef(false);

  useEffect(() => {
    let cancelled = false;
    logStartupPhase("frontend.license.fetch.begin");
    void controller.fetchSnapshot().then((snapshot) => {
      if (cancelled) return;
      logStartupPhase("frontend.license.fetch.end");
      setStatus(snapshot.status);
      setError(snapshot.error);
      setGateBlocks(snapshot.gateBlocks);
      setLoading(false);
      if (snapshot.error && !didNotifyError.current) {
        didNotifyError.current = true;
        toast.error(snapshot.error);
      }
      if (!snapshot.error) {
        didNotifyError.current = false;
      }
    });
    return () => {
      cancelled = true;
    };
  }, [controller, reloadToken]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setInterval(() => {
      void controller.fetchSnapshot().then((snapshot) => {
        if (cancelled) return;
        setStatus(snapshot.status);
        setError(snapshot.error);
        setGateBlocks(snapshot.gateBlocks);
        if (snapshot.error && !didNotifyError.current) {
          didNotifyError.current = true;
          toast.error(snapshot.error);
        }
        if (!snapshot.error) {
          didNotifyError.current = false;
        }
      });
    }, LICENSE_REFRESH_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [controller]);

  function refresh() {
    didNotifyError.current = false;
    setLoading(true);
    setReloadToken((value) => value + 1);
  }

  return { status, loading, error, gateBlocks, refresh };
}
