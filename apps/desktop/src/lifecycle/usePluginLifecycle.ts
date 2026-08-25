/**
 * 插件生命周期 — 启动时检测安装状态，下载进度只走事件。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */

import { useEffect, useRef } from "react";

import { listenPluginProgress } from "@desk/platform/events/plugin";
import { usePluginStore } from "../app/settings/plugin";

function toError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * 应用启动时拉取插件列表，并订阅 `plugin/progress` 驱动进度条。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */
export function usePluginLifecycle(): void {
  const started = useRef(false);
  const load = usePluginStore((state) => state.load);
  const applyProgress = usePluginStore((state) => state.applyProgress);

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void listenPluginProgress((payload) => {
      applyProgress(payload);
    })
      .then((fn) => {
        if (cancelled) {
          fn();
          return;
        }
        unlisten = fn;
      })
      .catch((error) => {
        console.warn(`订阅插件下载进度失败 error=${toError(error)}`);
      });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [applyProgress]);
}
