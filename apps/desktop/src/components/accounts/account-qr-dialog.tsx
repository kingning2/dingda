/**
 * 业务账号扫码登录弹窗（共享）— 显示二维码并轮询 sidecar 状态。
 *
 * 与平台无关：只消费 `platform` 与文案 props，不含任何平台分支。
 *
 * @author Xiaoman
 * @created 2026-08-13
 */

import { useEffect, useRef, useState } from "react";
import { Button, Dialog, DialogContent } from "@desk/ui";
import {
  accountQrCancel,
  accountQrCheck,
  accountQrStart,
  type AccountPlatform,
} from "@desk/platform/ipc/account";

type QrStatus =
  | "ready"
  | "waiting"
  | "scanned"
  | "confirmed"
  | "success"
  | "expired"
  | "failed"
  | "refreshed";

/**
 * 扫码登录弹窗：显示二维码并轮询 sidecar 状态。
 *
 * @author Xiaoman
 * @created 2026-08-13
 *
 * @param open - 是否打开
 * @param onClose - 关闭
 * @param onSuccess - 登录成功（账号已落库）
 * @param platform - `xianyu` / `ali1688`
 * @param title - 标题
 * @param hint - 等待扫码提示
 */
export function AccountQrDialog({
  open,
  onClose,
  onSuccess,
  platform,
  title = "扫码登录",
  hint = "请扫码登录",
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  platform: AccountPlatform;
  title?: string;
  hint?: string;
}) {
  const [status, setStatus] = useState<QrStatus>("ready");
  const [qrBase64, setQrBase64] = useState<string | null>(null);
  const [message, setMessage] = useState("正在生成二维码…");
  const sessionRef = useRef<string | null>(null);
  const cancelledRef = useRef(false);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    if (startedRef.current) {
      cancelledRef.current = false;
      return () => {
        cancelledRef.current = true;
      };
    }
    startedRef.current = true;
    cancelledRef.current = false;

    void accountQrStart(undefined, platform)
      .then((result) => {
        if (cancelledRef.current) {
          return;
        }
        if (!result.ok || !result.qr_base64) {
          setStatus("failed");
          setMessage(result.detail ?? "二维码生成失败");
          return;
        }
        sessionRef.current = result.session_id;
        setQrBase64(result.qr_base64);
        setStatus("waiting");
        setMessage(hint);
      })
      .catch((error) => {
        if (!cancelledRef.current) {
          setStatus("failed");
          setMessage(error instanceof Error ? error.message : String(error));
        }
      });

    return () => {
      cancelledRef.current = true;
      const sessionId = sessionRef.current;
      if (sessionId) {
        void accountQrCancel(sessionId, platform).catch(() => {});
      }
    };
  }, [open, hint, platform]);

  useEffect(() => {
    if (!open || !qrBase64 || status === "success") {
      return;
    }
    const timer = window.setInterval(async () => {
      if (!sessionRef.current) {
        return;
      }
      try {
        const result = await accountQrCheck(sessionRef.current, platform);
        if (cancelledRef.current) {
          return;
        }
        const nextStatus = result.status as QrStatus;
        switch (nextStatus) {
          case "waiting":
            setStatus("waiting");
            setMessage(hint);
            break;
          case "refreshed":
            if (result.qr_base64) {
              setQrBase64(result.qr_base64);
            }
            setStatus("waiting");
            setMessage(hint);
            break;
          case "scanned":
          case "confirmed":
            setStatus(nextStatus);
            setMessage("已扫码，请在手机确认登录");
            break;
          case "success":
            setStatus("success");
            setMessage("登录成功！");
            window.clearInterval(timer);
            onSuccess();
            onClose();
            break;
          case "expired":
            setStatus("expired");
            setMessage("二维码已过期，请重新打开");
            window.clearInterval(timer);
            break;
          case "failed":
            setStatus("failed");
            setMessage(result.detail ?? "登录失败");
            window.clearInterval(timer);
            break;
          default:
            setStatus("waiting");
            setMessage("等待扫码…");
        }
      } catch (error) {
        if (!cancelledRef.current) {
          setMessage(error instanceof Error ? error.message : String(error));
        }
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [open, qrBase64, status, onSuccess, onClose, hint, platform]);

  const isTerminal = status === "success" || status === "expired" || status === "failed";

  async function handleCancel() {
    cancelledRef.current = true;
    if (sessionRef.current) {
      try {
        await accountQrCancel(sessionRef.current, platform);
      } catch {
        // 忽略取消错误。
      }
    }
    onClose();
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isTerminal) {
          void handleCancel();
        }
      }}
    >
      <DialogContent className="w-[340px] max-w-[90vw]">
        <div className="flex flex-col items-center gap-4 p-4">
          <h3 className="text-[length:var(--text-lg)] font-semibold tracking-tight">{title}</h3>

          {!qrBase64 && status === "ready" ? (
            <p className="py-10 text-[length:var(--text-sm)] text-muted-foreground">正在生成二维码…</p>
          ) : qrBase64 ? (
            <img
              src={qrBase64}
              alt="登录二维码"
              className="size-56 rounded-[var(--radius-lg)] border border-border object-contain"
            />
          ) : (
            <div className="flex size-56 items-center justify-center rounded-[var(--radius-lg)] border border-dashed border-border">
              <p className="px-4 text-center text-[length:var(--text-sm)] text-muted-foreground">
                {message}
              </p>
            </div>
          )}

          {qrBase64 ? (
            <p
              className={`text-center text-[length:var(--text-sm)] ${
                status === "scanned" || status === "confirmed"
                  ? "text-amber-600"
                  : status === "failed" || status === "expired"
                    ? "text-destructive"
                    : status === "success"
                      ? "text-emerald-600"
                      : "text-muted-foreground"
              }`}
            >
              {message}
            </p>
          ) : null}

          <div className="flex w-full justify-center gap-2">
            {isTerminal ? (
              <Button onClick={onClose}>关闭</Button>
            ) : (
              <Button variant="ghost" onClick={() => void handleCancel()}>
                取消
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
