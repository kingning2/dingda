import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { finishBootSplash, preloadAppHome } from "@/lib/app-preload";
import {
  fetchServerStatus,
  getInitialServerStatus,
  subscribeServerEvents,
  type ServerStatus,
} from "@/lib/server";
import { setApiBaseUrl } from "@/lib/http-client";

const ServerContext = createContext<ServerStatus>(getInitialServerStatus());

export function useServer(): ServerStatus {
  return useContext(ServerContext);
}

export function ServerProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ServerStatus>(getInitialServerStatus);
  const [homeReady, setHomeReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    const sync = async () => {
      const initial = await fetchServerStatus();
      if (!cancelled) setStatus(initial);
      unlisten = await subscribeServerEvents((next) => {
        if (!cancelled) setStatus(next);
      });
    };

    void sync();

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  useEffect(() => {
    setApiBaseUrl(status.apiBaseUrl);

    // Server 起不来也卸启动屏，避免一直卡在 splash
    if (status.phase === "error") {
      setHomeReady(true);
      finishBootSplash();
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
      setHomeReady(true);
      finishBootSplash();
    })();

    return () => {
      cancelled = true;
    };
  }, [status.ready, status.apiBaseUrl, status.phase]);

  const value = useMemo(() => status, [status]);

  // 预加载完成前不挂路由，启动屏继续挡着
  if (!homeReady) return null;

  return <ServerContext.Provider value={value}>{children}</ServerContext.Provider>;
}
