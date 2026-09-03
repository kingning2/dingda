import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  fetchBackendStatus,
  getInitialBackendStatus,
  kickBackendWarmup,
  subscribeBackendEvents,
  type BackendStatus,
} from "@/lib/backend";

const BackendContext = createContext<BackendStatus>(getInitialBackendStatus());

export function useBackend(): BackendStatus {
  return useContext(BackendContext);
}

export function BackendProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>(getInitialBackendStatus);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    const sync = async () => {
      const initial = await fetchBackendStatus();
      if (!cancelled) setStatus(initial);
      unlisten = await subscribeBackendEvents((next) => {
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
    if (!status.ready || !status.apiBaseUrl) return;
    void kickBackendWarmup(status.apiBaseUrl);
  }, [status.ready, status.apiBaseUrl]);

  const value = useMemo(() => status, [status]);

  return <BackendContext.Provider value={value}>{children}</BackendContext.Provider>;
}
