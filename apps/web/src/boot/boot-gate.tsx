import { useEffect, useState, type ReactNode } from "react";

import { dismissBootSplash } from "@v2/runtime/dismiss-boot-splash";
import { useServer } from "@v2/runtime/server-provider";

import { preloadAppHome } from "./preload";

/**
 * 启动闸门：首页数据预加载完成前不挂路由，HTML 启动屏继续挡着。
 *
 * 这段逻辑早先长在 @v2/runtime 的 ServerProvider 里，但它要调 ui-agent /
 * ui-account 的发现逻辑 —— 基座包依赖业务包，方向是反的。移到应用装配层后，
 * runtime 回归纯基座，启动时序由本组件统一掌管。
 */
export function BootGate({ children }: { children: ReactNode }) {
  const status = useServer();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Server 起不来也卸启动屏，避免一直卡在 splash
    if (status.phase === "error") {
      setReady(true);
      dismissBootSplash();
      return;
    }

    if (!status.ready || !status.apiBaseUrl) return;

    let cancelled = false;
    void (async () => {
      try {
        await preloadAppHome();
      } catch {
        // 预热失败也进页，首页可再刷
      }
      if (cancelled) return;
      setReady(true);
      dismissBootSplash();
    })();

    return () => {
      cancelled = true;
    };
  }, [status.ready, status.apiBaseUrl, status.phase]);

  if (!ready) return null;

  return <>{children}</>;
}
