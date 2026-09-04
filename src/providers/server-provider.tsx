import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  fetchServerStatus,
  getInitialServerStatus,
  kickServerWarmup,
  subscribeServerEvents,
  type ServerStatus,
} from "@/lib/server";
import { setApiBaseUrl } from "@/lib/http-client";
import { refreshDiscoveryOnServerReady } from "@/lib/discovery-scan";

const ServerContext = createContext<ServerStatus>(getInitialServerStatus());

export function useServer(): ServerStatus {
  return useContext(ServerContext);
}

export function ServerProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ServerStatus>(getInitialServerStatus);

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
    if (!status.ready || !status.apiBaseUrl) return;
    void kickServerWarmup();
    void refreshDiscoveryOnServerReady();
  }, [status.ready, status.apiBaseUrl]);

  const value = useMemo(() => status, [status]);

  return <ServerContext.Provider value={value}>{children}</ServerContext.Provider>;
}
