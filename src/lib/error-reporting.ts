import { invoke } from "@tauri-apps/api/core";

type FrontendErrorPayload = {
  kind: "window-error" | "unhandled-rejection" | "react-error";
  message: string;
  source?: string;
  lineno?: number;
  colno?: number;
  stack?: string;
};

let installed = false;

async function reportFrontendError(payload: FrontendErrorPayload): Promise<void> {
  try {
    console.error("【前端发生错误】", payload);
    await invoke("log_frontend_error", { payload });
  } catch (error) {
    console.error("【前端发生错误】", error, payload);
  }
}

function normalizeUnknownError(error: unknown): { message: string; stack?: string } {
  if (error instanceof Error) {
    return { message: error.message, stack: error.stack };
  }
  if (typeof error === "string") {
    return { message: error };
  }
  return { message: String(error) };
}

export function installGlobalErrorReporting(): void {
  if (installed) return;
  installed = true;

  window.addEventListener("error", (event) => {
    const details = normalizeUnknownError(event.error ?? event.message);
    void reportFrontendError({
      kind: "window-error",
      message: details.message,
      source: event.filename || undefined,
      lineno: event.lineno || undefined,
      colno: event.colno || undefined,
      stack: details.stack,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const details = normalizeUnknownError(event.reason);
    void reportFrontendError({
      kind: "unhandled-rejection",
      message: details.message,
      stack: details.stack,
    });
  });
}

export async function reportReactError(
  error: Error,
  componentStack?: string,
): Promise<void> {
  await reportFrontendError({
    kind: "react-error",
    message: error.message,
    stack: [error.stack, componentStack].filter(Boolean).join("\n"),
  });
}
