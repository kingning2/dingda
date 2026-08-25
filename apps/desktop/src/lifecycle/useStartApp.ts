/**
 * 应用启动生命周期。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */

import { useEffect, useRef } from "react";

import { logStartupPhase } from "./startup-log";

/**
 * 桌面应用前端启动钩子（幂等；StrictMode 下只上报一次）。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */
export function useStartApp(): void {
  const started = useRef(false);

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    logStartupPhase("frontend.shell.ready");
  }, []);
}
