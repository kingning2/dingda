/**
 * 任务副驾 Provider — 端点发现 + agent 组装 + 上下文注入。
 *
 * 等待 sidecar 辅助 HTTP 就绪（最多 ~30s），就绪后构造 TaskCopilotAgent
 * 并挂入 CopilotKit（selfManagedAgents）；子页面经 `useCopilotTaskContext`
 * 注入任务快照（任务列表 / 当前 run 详情）。
 */

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { copilotEndpoint } from "@desk/platform";
import type { AiIpcConfigResponse } from "@desk/contracts";
import { aiConfigGet } from "@desk/platform/ipc/ai";

import { TaskCopilotAgent, type TaskCopilotContext } from "./task-copilot-agent";

type SetCopilotContext = (context: TaskCopilotContext) => void;

const CopilotContextSetterContext = createContext<SetCopilotContext>(() => {});

/** 注入任务上下文快照（任务列表 / 当前 run 详情 / AI 凭据以外的扩展）。 */
export function useCopilotTaskContext(state?: Record<string, unknown>): void {
  const setContext = useContext(CopilotContextSetterContext);
  useEffect(() => {
    setContext({ state });
  }, [setContext, state]);
}

async function resolveCredentials(): Promise<TaskCopilotContext["forwardedProps"]> {
  try {
    const config: AiIpcConfigResponse = await aiConfigGet();
    const account = config.accounts[0];
    if (!account) {
      return undefined;
    }
    const provider = config.providers.find((item) => item.id === account.provider_id);
    return {
      default_base_url: provider?.base_url ?? "",
      default_api_key: account.api_key ?? "",
      default_model: account.default_model ?? provider?.default_model ?? "",
    };
  } catch {
    // 后端未就绪：agent 会以 RUN_ERROR 提示配置 AI 账号。
    return undefined;
  }
}

const ENDPOINT_MAX_ATTEMPTS = 30;
const ENDPOINT_RETRY_MS = 1_000;

/**
 * 任务副驾范围：需在任务中心 / 详情（对话流）页面外层挂载。
 */
export function TaskCopilotProvider({ children }: { children: ReactNode }) {
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [agent, setAgent] = useState<TaskCopilotAgent | null>(null);
  const contextRef = useRef<TaskCopilotContext>({});

  const setContext = useMemo<SetCopilotContext>(() => (context) => {
    contextRef.current = { ...contextRef.current, ...context };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;
    const tick = () => {
      if (cancelled) {
        return;
      }
      void copilotEndpoint()
        .then((url) => {
          if (cancelled) {
            return;
          }
          if (url) {
            setEndpoint(url);
            return;
          }
          attempt += 1;
          if (attempt >= ENDPOINT_MAX_ATTEMPTS) {
            setUnavailable(true);
            return;
          }
          window.setTimeout(tick, ENDPOINT_RETRY_MS);
        })
        .catch(() => {
          if (!cancelled) {
            attempt += 1;
            if (attempt >= ENDPOINT_MAX_ATTEMPTS) {
              setUnavailable(true);
            } else {
              window.setTimeout(tick, ENDPOINT_RETRY_MS);
            }
          }
        });
    };
    tick();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!endpoint || agent) {
      return;
    }
    const next = new TaskCopilotAgent({ url: endpoint }, () => contextRef.current);
    setAgent(next);
  }, [endpoint, agent]);

  useEffect(() => {
    if (!endpoint) {
      return;
    }
    void resolveCredentials().then((forwardedProps) => {
      if (forwardedProps) {
        contextRef.current = { ...contextRef.current, forwardedProps };
      }
    });
  }, [endpoint]);

  if (!endpoint || !agent) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-muted-foreground">
        {unavailable
          ? "副驾服务不可用：后台服务未就绪或启动失败，请稍后重试"
          : "正在连接副驾服务…"}
      </div>
    );
  }

  return (
    <CopilotContextSetterContext.Provider value={setContext}>
      <CopilotKitProvider selfManagedAgents={{ task_copilot: agent }}>
        {children}
      </CopilotKitProvider>
    </CopilotContextSetterContext.Provider>
  );
}
