/**
 * 设置弹窗 — 关于与版本信息。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { useEffect, useState } from "react";
import { Card } from "@desk/ui";
import { appVersion } from "@desk/platform/ipc/app";

/**
 * 关于与版本面板。
 *
 * @author Xiaoman
 * @created 2026-08-20
 *
 * @returns 面板节点
 */
export function AboutPanel() {
  const [version, setVersion] = useState<string | null>(null);
  const [versionError, setVersionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void appVersion()
      .then((value) => {
        if (!cancelled) {
          setVersion(value);
          setVersionError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setVersionError(error instanceof Error ? error.message : String(error));
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex w-full max-w-lg flex-col gap-5">
      <div className="flex items-center gap-4">
        <img
          src="/logo.webp"
          alt=""
          className="size-14 shrink-0 rounded-[var(--radius-md)] object-cover shadow-sm"
        />
        <div className="min-w-0">
          <p className="font-display text-[length:var(--text-lg)] font-semibold tracking-tight">
            {__DINGDA_APP_BRAND_TITLE__}
          </p>
          <p className="mt-1 text-[length:var(--text-sm)] text-muted-foreground">
            本地优先的 AI 智能客服桌面平台
          </p>
        </div>
      </div>

      <Card className="gap-3 p-4">
        <p className="text-[length:var(--text-sm)] font-medium">当前版本</p>
        <p className="font-mono text-[length:var(--text-sm)] text-muted-foreground">
          {version ? `v${version}` : versionError ? "读取失败" : "加载中…"}
        </p>
        {versionError ? (
          <p className="text-[length:var(--text-sm)] text-red-600 dark:text-red-400">
            {versionError}
          </p>
        ) : null}
      </Card>
    </div>
  );
}
