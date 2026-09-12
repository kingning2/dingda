import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import type { AccountQrCheckResponse } from "@v2/contracts/account";
import type { AccountPanelConfig } from "./types";
import { checkAccountQrLogin, cancelAccountQrLogin, startAccountQrLogin } from "@/lib/account-qr";
import { getHostCapabilities } from "@/lib/capabilities";
import { useServer } from "@/providers/server-provider";
import { Button } from "@v2/ui-primitives/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@v2/ui-primitives/dialog";

interface AccountQrDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (result: AccountQrCheckResponse) => void;
  config: AccountPanelConfig;
  title?: string;
  hint?: string;
}

const MOCK_QR_FLOW: AccountQrCheckResponse[] = [
  { ok: true, status: "waiting", detail: null },
  { ok: true, status: "scanned", detail: "已扫码，请在手机确认登录" },
  {
    ok: true,
    status: "success",
    detail: "登录成功！",
    account_id: "mock:new",
    display_name: "模拟账号",
    cookie: "mock-cookie",
  },
];

function messageFromResponse(response: AccountQrCheckResponse, fallback: string): string {
  return response.detail?.trim() || fallback;
}

/** 规范化扫码图：空格可能是被弄坏的 `+`，再交给 blob URL 显示。 */
function normalizeQrBase64(qrBase64: string | null | undefined): string | null {
  if (!qrBase64?.trim()) return null;
  let raw = qrBase64.trim();
  if (raw.startsWith("data:image")) {
    const comma = raw.indexOf(",");
    raw = comma >= 0 ? raw.slice(comma + 1) : "";
  }
  // 传输中 `+` 偶发变空格；先还原再去掉其余空白
  const cleaned = raw.replace(/ /g, "+").replace(/\s+/g, "");
  return cleaned.length > 80 ? cleaned : null;
}

function qrPayloadToObjectUrl(payload: string): string | null {
  try {
    const binary = atob(payload);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    // PNG / JPEG 魔数粗检，避免把坏 base64 塞进 img
    const isPng =
      bytes[0] === 0x89 &&
      bytes[1] === 0x50 &&
      bytes[2] === 0x4e &&
      bytes[3] === 0x47;
    const isJpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
    if (!isPng && !isJpeg) return null;
    const blob = new Blob([bytes], {
      type: isPng ? "image/png" : "image/jpeg",
    });
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

/** 扫码登录：Server 就绪走 HTTP；仅桌面壳启动中显示等待态。 */
export function AccountQrDialog({
  open,
  onClose,
  onSuccess,
  config,
  title = "扫码登录",
  hint,
}: AccountQrDialogProps) {
  const server = useServer();
  const { desktop } = getHostCapabilities();
  const defaultHint = `请用 ${config.appName} App 扫码`;
  const useLiveApi = server.ready && Boolean(server.apiBaseUrl);
  const waitingServer = desktop && !server.ready && server.phase !== "error";
  const serverError = desktop && server.phase === "error" ? server.error : null;

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AccountQrCheckResponse | null>(null);
  const [flowIndex, setFlowIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [imageBroken, setImageBroken] = useState(false);
  const sessionIdRef = useRef<string | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const onSuccessRef = useRef(onSuccess);
  const onCloseRef = useRef(onClose);
  const lastQrRef = useRef<string | null>(null);

  useEffect(() => {
    onSuccessRef.current = onSuccess;
  }, [onSuccess]);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const payload = normalizeQrBase64(response?.qr_base64);
    if (!payload || payload === lastQrRef.current) {
      if (!payload) {
        lastQrRef.current = null;
        setImageSrc((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return null;
        });
        setImageBroken(false);
      }
      return;
    }
    const next = qrPayloadToObjectUrl(payload);
    if (!next) {
      lastQrRef.current = null;
      setImageBroken(true);
      setImageSrc((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      return;
    }
    lastQrRef.current = payload;
    setImageBroken(false);
    setImageSrc((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return next;
    });
  }, [response?.qr_base64]);

  useEffect(() => {
    if (!open) {
      setLoading(false);
      setResponse(null);
      setFlowIndex(0);
      setError(null);
      setImageBroken(false);
      lastQrRef.current = null;
      setImageSrc((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      sessionIdRef.current = null;
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }

    if (!useLiveApi) {
      if (waitingServer) {
        setLoading(true);
        setResponse(null);
        setError(null);
        return;
      }
      setLoading(true);
      const timer = window.setTimeout(() => {
        setLoading(false);
        setResponse({ ok: true, status: "waiting", detail: hint ?? defaultHint });
      }, 600);
      return () => window.clearTimeout(timer);
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const started = await startAccountQrLogin(config.platform);
        if (cancelled) {
          if (started.session_id) {
            void cancelAccountQrLogin(started.session_id);
          }
          return;
        }
        sessionIdRef.current = started.session_id ?? null;
        setResponse({
          ...started,
          detail: started.detail ?? hint ?? defaultHint,
        });
        setLoading(false);

        if (!started.session_id) return;

        const pollOnce = async () => {
          try {
            const checked = await checkAccountQrLogin(started.session_id!);
            if (cancelled) return;
            // 轮询偶发不带图时保留上一张，避免闪成裂图占位
            setResponse((prev) => ({
              ...checked,
              qr_base64: checked.qr_base64 ?? prev?.qr_base64 ?? null,
            }));

            if (checked.status === "success") {
              if (pollTimerRef.current !== null) {
                window.clearInterval(pollTimerRef.current);
                pollTimerRef.current = null;
              }
              window.setTimeout(() => {
                onSuccessRef.current(checked);
                onCloseRef.current();
              }, 400);
            } else if (
              checked.status === "failed" ||
              checked.status === "expired"
            ) {
              if (pollTimerRef.current !== null) {
                window.clearInterval(pollTimerRef.current);
                pollTimerRef.current = null;
              }
            }
          } catch (pollError) {
            if (cancelled) return;
            setError(pollError instanceof Error ? pollError.message : "轮询失败");
            if (pollTimerRef.current !== null) {
              window.clearInterval(pollTimerRef.current);
              pollTimerRef.current = null;
            }
          }
        };

        void pollOnce();
        pollTimerRef.current = window.setInterval(() => {
          void pollOnce();
        }, 1500);
      } catch (startError) {
        if (cancelled) return;
        setLoading(false);
        setError(startError instanceof Error ? startError.message : "启动扫码失败");
      }
    })();

    return () => {
      cancelled = true;
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      const sessionId = sessionIdRef.current;
      sessionIdRef.current = null;
      if (sessionId) {
        void cancelAccountQrLogin(sessionId);
      }
    };
  }, [open, useLiveApi, waitingServer, server.apiBaseUrl, config.platform, hint, defaultHint]);

  const status = response?.status ?? (loading ? "ready" : "");
  const message = error
    ? error
    : serverError
      ? `Server 启动失败：${serverError}`
      : waitingServer
      ? "Server 启动中，请稍候…"
      : loading && useLiveApi
        ? "正在生成二维码…"
      : loading
      ? "正在生成二维码…"
      : response
        ? messageFromResponse(response, hint ?? defaultHint)
        : "";
  function handleSimulateScan() {
    const next = MOCK_QR_FLOW[Math.min(flowIndex + 1, MOCK_QR_FLOW.length - 1)];
    setFlowIndex((index) => Math.min(index + 1, MOCK_QR_FLOW.length - 1));
    setResponse({ ...next, detail: next.detail ?? hint ?? defaultHint });

    if (next.status === "success") {
      window.setTimeout(() => {
        onSuccess(next);
        onClose();
      }, 600);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          onClose();
        }
      }}
    >
      <DialogContent className="w-[340px] max-w-[90vw]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center gap-4 py-2">
          {loading ? (
            <div className="flex size-56 items-center justify-center rounded-xl border border-dashed border-border">
              <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
          ) : imageSrc && !imageBroken ? (
            <div className="flex size-56 items-center justify-center overflow-hidden rounded-xl border border-border bg-white p-3">
              <img
                src={imageSrc}
                alt="登录二维码"
                className="size-full object-contain"
                onError={() => setImageBroken(true)}
              />
            </div>
          ) : (
            <div className="flex size-56 items-center justify-center rounded-xl border border-dashed border-border text-center text-xs text-muted-foreground">
              {useLiveApi
                ? imageBroken
                  ? "二维码无法显示，请重试"
                  : "二维码生成失败"
                : "UI 占位"}
            </div>
          )}

          <p
            className={`text-center text-sm ${
              status === "scanned"
                ? "text-amber-600"
                : status === "failed" || status === "expired" || error || serverError
                  ? "text-destructive"
                  : status === "success"
                    ? "text-emerald-600"
                    : "text-muted-foreground"
            }`}
          >
            {message}
          </p>

          {!useLiveApi && !waitingServer && !serverError ? (
            <p className="text-center text-xs text-amber-700">
              当前为演示模式（浏览器 或 后端未就绪），扫码为 UI 占位
            </p>
          ) : null}

          {!useLiveApi && status === "waiting" ? (
            <Button variant="outline" onClick={handleSimulateScan}>
              模拟扫码成功
            </Button>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
