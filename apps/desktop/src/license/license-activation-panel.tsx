/**
 * 设置内的软件激活面板（非全屏遮罩）。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { Button, Input, cn } from "@desk/ui";
import {
  formatLicenseExpiresAt,
  formatLicenseRemaining,
} from "./format-license-remaining";
import { useLicenseGateContext } from "./license-gate-context";
import { useLicenseActivate } from "./use-license-activate";

/**
 * 设置弹窗内的激活 / 授权状态面板。
 *
 * @author Xiaoman
 * @created 2026-08-20
 *
 * @returns 面板节点
 */
export function LicenseActivationPanel() {
  const { status, loading, refresh } = useLicenseGateContext();
  const {
    machineCode,
    token,
    setToken,
    busy,
    message,
    copyMachineCode,
    activateWithToken,
  } = useLicenseActivate(() => {
    void refresh();
  });

  const machineCodeDisplay =
    machineCode.trim() || status?.machineCode?.trim() || "";

  if (loading) {
    return (
      <p className="text-[length:var(--text-sm)] text-muted-foreground">正在读取授权状态…</p>
    );
  }

  if (!status?.gateEnabled) {
    return (
      <div className="max-w-md space-y-2">
        <p className="font-medium text-foreground">当前版本无需激活</p>
        <p className="text-[length:var(--text-sm)] leading-relaxed text-muted-foreground">
          本构建未启用授权闸门，全部功能可直接使用。
        </p>
      </div>
    );
  }

  if (status.activated) {
    const nowSec = Math.floor(Date.now() / 1000);
    const expiresAt = status.expiresAt;
    const remaining =
      expiresAt != null ? formatLicenseRemaining(expiresAt, nowSec) : null;

    return (
      <div className="max-w-md space-y-3">
        <p className="font-medium text-foreground">已激活</p>
        <p className="text-[length:var(--text-sm)] text-muted-foreground">
          付费功能已解锁；免费功能始终可用。
        </p>
        {status.product ? (
          <p className="text-[length:var(--text-sm)]">
            产品 <span className="font-medium">{status.product}</span>
          </p>
        ) : null}
        {expiresAt != null ? (
          <>
            <p className="text-[length:var(--text-sm)] text-muted-foreground">
              到期时间 {formatLicenseExpiresAt(expiresAt)}
            </p>
            {remaining ? (
              <p
                className={cn(
                  "text-[length:var(--text-sm)] font-medium",
                  remaining.expired
                    ? "text-destructive"
                    : remaining.urgent
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-emerald-600 dark:text-emerald-400",
                )}
              >
                {remaining.text}
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-[length:var(--text-sm)] text-muted-foreground">永久授权</p>
        )}
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-4">
      <p className="text-[length:var(--text-sm)] leading-relaxed text-muted-foreground">
        未激活也可使用基础功能。将本机码发给管理员获取激活码，粘贴后即可解锁扫码登录、AI 助手等付费能力。
      </p>

      <div className="flex flex-col gap-2">
        <label htmlFor="license-machine-code" className="text-[length:var(--text-sm)] font-medium">
          本机码
        </label>
        <div className="flex gap-2">
          <Input
            id="license-machine-code"
            readOnly
            value={machineCodeDisplay || "加载中…"}
            className="min-w-0 flex-1 font-mono text-[length:var(--text-xs)]"
          />
          <Button
            type="button"
            variant="secondary"
            onClick={() => void copyMachineCode()}
            disabled={!machineCodeDisplay || busy}
          >
            复制
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="license-activation-code" className="text-[length:var(--text-sm)] font-medium">
          激活码
        </label>
        <Input
          id="license-activation-code"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="da-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
          disabled={busy}
          className="font-mono"
          onKeyDown={(event) => {
            if (event.key === "Enter" && token.trim() && !busy) {
              void activateWithToken();
            }
          }}
        />
      </div>

      <Button disabled={busy || !token.trim()} onClick={() => void activateWithToken()}>
        {busy ? "校验中…" : "激活"}
      </Button>

      {message ? (
        <p
          role="status"
          aria-live="polite"
          className={cn(
            "text-[length:var(--text-sm)]",
            message.includes("成功") ? "text-foreground" : "text-destructive",
          )}
        >
          {message}
        </p>
      ) : null}
    </div>
  );
}
