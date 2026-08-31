/** 聊天文案。 */
export const CHAT_COPY = {
  welcome: "今天有什么可以帮你？",
  placeholder: "询问任务进度、发起比价…",
  disclaimer: "AI 可能会出错，重要信息请自行核实。",
  think: "思考",
  toolRunning: "执行中…",
  toolDone: "已完成",
  deepDiving: "深入分析中…",
  emptyReply: "（无回复内容）",
} as const;

const TOOL_LABELS: Record<string, string> = {
  start_price_compare: "发起比价",
  control_run: "控制任务",
};

export function toolDisplayName(name: string): string {
  return TOOL_LABELS[name] ?? name;
}

export function toolSummary(name: string, args: string, result?: string, running?: boolean): string {
  if (running) {
    return args.trim() || CHAT_COPY.toolRunning;
  }

  if (name === "start_price_compare" && result) {
    try {
      const data = JSON.parse(result) as { ok?: boolean; run_id?: string; state?: string };
      if (data.ok && data.run_id) {
        return "任务已启动，执行过程见下方";
      }
      if (data.ok === false) {
        return "启动失败";
      }
    } catch {
      // fall through
    }
  }

  if (result) {
    const trimmed = result.trim();
    return trimmed.length > 120 ? `${trimmed.slice(0, 120)}…` : trimmed;
  }
  return args.trim() || CHAT_COPY.toolDone;
}

export function toolResultBody(name: string, result?: string, args?: string): string | null {
  if (name === "start_price_compare") {
    return null;
  }
  if (result && result.includes("\n")) {
    return result;
  }
  if (args && args.includes("\n")) {
    return args;
  }
  return null;
}
