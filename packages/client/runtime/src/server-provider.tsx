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
  subscribeServerEvents,
  type ServerStatus,
} from "./server";
import { setApiBaseUrl } from "./http-client";

const ServerContext = createContext<ServerStatus>(getInitialServerStatus());

export function useServer(): ServerStatus {
  return useContext(ServerContext);
}

/**
 * 只做一件事：订阅 Server 状态、把 baseUrl 注入传输层、向下提供 useServer。
 *
 * 启动预载（拉首页数据、卸启动屏）刻意不在这里。那套编排要调 ui-agent /
 * ui-account 的发现逻辑，属于应用装配层（apps/web/src/boot）；放在基座包里
 * 会让 @v2/runtime 反向依赖业务包，依赖方向就反了。
 */
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
  }, [status.apiBaseUrl]);

  const value = useMemo(() => status, [status]);

  return <ServerContext.Provider value={value}>{children}</ServerContext.Provider>;
}
