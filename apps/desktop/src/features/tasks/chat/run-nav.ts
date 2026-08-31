/** 工具 `start_price_compare` 返回 run_id 后的导航回调。 */

let onRunStarted: ((runId: string) => void) | null = null;

export function registerRunStarted(handler: (runId: string) => void): () => void {
  onRunStarted = handler;
  return () => {
    if (onRunStarted === handler) {
      onRunStarted = null;
    }
  };
}

function parseRunIdFromToolResult(content: string): string | null {
  try {
    const data = JSON.parse(content) as { ok?: boolean; run_id?: string };
    if (data.ok === false) {
      return null;
    }
    const runId = data.run_id?.trim();
    return runId || null;
  } catch {
    return null;
  }
}

export function tryNotifyPriceCompareStarted(
  toolName: string | undefined,
  content: string | undefined,
): void {
  if (toolName !== "start_price_compare" || !content) {
    return;
  }
  const runId = parseRunIdFromToolResult(content);
  if (runId) {
    onRunStarted?.(runId);
  }
}
