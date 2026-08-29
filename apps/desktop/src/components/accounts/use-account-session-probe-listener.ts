/**
 * 订阅 Rust 启动生命周期推送的账号探活结果，写入前端缓存并广播。
 */

import { useEffect, useRef } from "react";
import { listenAccountsSessionProbed } from "@desk/platform/events";
import { dispatchAccountsSessionProbed } from "./account-session-events";
import { recordSessionProbe } from "./use-connected-accounts";

/** 应用级：监听 Rust 后台探活结果，不发起探活 IPC。 */
export function useAccountSessionProbeListener(): void {
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) {
      return;
    }
    startedRef.current = true;

    let unlisten: (() => void) | undefined;
    let cancelled = false;

    void listenAccountsSessionProbed((payload) => {
      for (const item of payload.probes) {
        recordSessionProbe(item.account_id, item.online);
      }
      dispatchAccountsSessionProbed();
    })
      .then((fn) => {
        if (cancelled) {
          fn();
          return;
        }
        unlisten = fn;
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);
}
