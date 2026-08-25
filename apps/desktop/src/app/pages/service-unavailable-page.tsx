/**
 * 503 服务不可用页 — 后端中断或授权状态拉取失败。
 */

import { Navigate } from "react-router";
import { Button } from "@desk/ui";
import { useLicenseGateContext } from "@license";
import { useErrorStore } from "../../lifecycle";

/**
 * 后端不可用或授权校验失败时的恢复页。
 */
export function ServiceUnavailablePage() {
  const { error, refresh } = useLicenseGateContext();
  const backendUnavailable = useErrorStore((state) => state.backendUnavailable);
  const setBackendUnavailable = useErrorStore((state) => state.setBackendUnavailable);

  if (!backendUnavailable && !error) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center gap-4 px-6">
      <div className="flex max-w-md flex-col items-center gap-2 text-center">
        <h1 className="text-[7rem] font-bold leading-tight tracking-tight">503</h1>
        <p className="text-[length:var(--text-lg)] font-medium text-foreground">服务暂不可用</p>
        <p className="text-[length:var(--text-sm)] text-muted-foreground">
          {error ?? "连接中断或后台服务正在恢复，请稍后重试。"}
        </p>
      </div>
      <Button
        onClick={() => {
          setBackendUnavailable(false);
          refresh();
        }}
      >
        重试
      </Button>
    </div>
  );
}
