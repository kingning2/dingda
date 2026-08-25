/**
 * 解锁流程容器 — 状态机 + 表单 + 视觉组合。
 *
 * 业务层只调用现有 [`LicenseActivationService`]，不触碰 IPC 契约。
 *
 * @author coisini
 * @created 2026-08-24
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, toast, useReducedMotion } from "@desk/ui";
import { Button, Input, cn } from "@desk/ui";

import { LicenseActivationService, type LicenseActivationResult } from "../license-activation-service";
import { SuccessReveal } from "./success-reveal";
import { UnlockStatus } from "./unlock-status";
import { UnlockSteps } from "./unlock-steps";
import { UnlockVisual } from "./unlock-visual";
import type { UnlockStatus as FlowStatus, UnlockStep } from "./types";

const VERIFYING_STEPS = ["读取设备信息", "校验激活码", "解锁付费能力"];
const UNLOCKING_STEPS = ["授权已验证", "账号已确认", "正在启用 AI 能力"];

/** 单步推进间隔。 */
const STEP_INTERVAL_MS = 480;
/** unlocking 状态持续时间。 */
const UNLOCKING_MS = 1100;

function initialSteps(labels: string[]): UnlockStep[] {
  return labels.map((label, index) => ({
    id: `${index}`,
    label,
    state: index === 0 ? "active" : "pending",
  }));
}

function markStep(steps: UnlockStep[], index: number): UnlockStep[] {
  return steps.map((step, i) => ({
    ...step,
    state: i < index ? "done" : i === index ? "active" : "pending",
  }));
}

function allDone(steps: UnlockStep[]): UnlockStep[] {
  return steps.map((step) => ({ ...step, state: "done" }));
}

export interface UnlockFlowProps {
  /** 进入工作区（授权刷新由页面层负责）。 */
  onEnter: () => void;
}

/**
 * Locked → Verifying → Unlocking → Ready / Error 的完整流程。
 *
 * @author coisini
 * @created 2026-08-24
 *
 * @param props.onEnter - 点击「进入 DingDa」回调
 */
export function UnlockFlow({ onEnter }: UnlockFlowProps) {
  const reducedMotion = useReducedMotion();
  const [service] = useState(() => new LicenseActivationService());
  const [status, setStatus] = useState<FlowStatus>("locked");
  const [machineCode, setMachineCode] = useState("");
  const [token, setToken] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [product, setProduct] = useState<string | null>(null);
  const [steps, setSteps] = useState<UnlockStep[]>(() => initialSteps(VERIFYING_STEPS));
  const [busy, setBusy] = useState(false);

  const runIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    void service
      .loadMachineCode()
      .then((code) => {
        if (!cancelled) {
          setMachineCode(code);
        }
      })
      .catch(() => {
        // 设备码加载失败不阻塞流程，激活时后端仍会校验。
      });
    return () => {
      cancelled = true;
    };
  }, [service]);

  const wait = useCallback(
    (ms: number) =>
      new Promise<void>((resolve) => {
        window.setTimeout(resolve, reducedMotion ? Math.min(ms, 80) : ms);
      }),
    [reducedMotion],
  );

  const start = useCallback(async () => {
    const trimmed = token.trim();
    if (!trimmed || busy) {
      return;
    }

    const runId = ++runIdRef.current;
    const alive = () => runIdRef.current === runId;

    setBusy(true);
    setErrorMessage(null);
    setStatus("verifying");
    setSteps(initialSteps(VERIFYING_STEPS));

    const resultPromise: Promise<LicenseActivationResult> = service.activateWithToken(trimmed);

    // 步骤推进与真实 IPC 并行；结果到达后收敛到终态。
    (async () => {
      for (let i = 1; i < VERIFYING_STEPS.length; i += 1) {
        await wait(STEP_INTERVAL_MS);
        if (!alive()) {
          return;
        }
        setSteps((current) => markStep(current, i));
      }
    })();

    const result = await resultPromise;
    if (!alive()) {
      return;
    }
    setBusy(false);

    if (!result.ok) {
      setErrorMessage(result.message);
      setStatus("error");
      return;
    }

    setProduct(result.status?.product ?? null);
    setSteps(allDone(initialSteps(VERIFYING_STEPS)));
    await wait(320);
    if (!alive()) {
      return;
    }

    setStatus("unlocking");
    setSteps(() => initialSteps(UNLOCKING_STEPS));
    for (let i = 1; i < UNLOCKING_STEPS.length; i += 1) {
      await wait(UNLOCKING_MS / UNLOCKING_STEPS.length);
      if (!alive()) {
        return;
      }
      setSteps((current) => markStep(current, i));
    }
    if (!alive()) {
      return;
    }

    setSteps(allDone(initialSteps(UNLOCKING_STEPS)));
    await wait(260);
    if (alive()) {
      setStatus("ready");
    }
  }, [busy, service, token, wait]);

  const retry = useCallback(() => {
    runIdRef.current += 1;
    setBusy(false);
    setErrorMessage(null);
    setStatus("locked");
  }, []);

  const copyMachineCode = useCallback(async () => {
    const message = await service.copyMachineCode();
    if (message.includes("已复制")) {
      toast.success(message);
      return;
    }
    toast.error(message);
  }, [service]);

  const showForm = status === "locked" || status === "verifying";

  return (
    <div className="flex w-full max-w-sm flex-col items-center gap-8">
      <UnlockVisual status={status} />
      <AnimatePresence mode="wait" initial={false}>
        {status === "ready" ? (
          <motion.div
            key="ready"
            initial={{ opacity: 0, scale: reducedMotion ? 1 : 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="flex w-full flex-col items-center gap-8"
          >
            <SuccessReveal product={product} />
            <Button className="w-full max-w-xs" onClick={onEnter}>
              进入 DingDa
            </Button>
          </motion.div>
        ) : (
          <motion.div
            key="flow"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="flex w-full flex-col items-center gap-6"
          >
            <UnlockStatus status={status} />

            {(status === "verifying" || status === "unlocking") && (
              <UnlockSteps steps={steps} />
            )}

            {showForm && (
              <form
                className="flex w-full flex-col gap-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void start();
                }}
              >
                {machineCode ? (
                  <div className="flex flex-col gap-2">
                    <label
                      htmlFor="unlock-machine-code"
                      className="text-[length:var(--text-sm)] font-medium text-foreground"
                    >
                      本机码
                    </label>
                    <div className="flex gap-2">
                      <Input
                        id="unlock-machine-code"
                        readOnly
                        value={machineCode}
                        className="min-w-0 flex-1 font-mono text-[length:var(--text-xs)]"
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => void copyMachineCode()}
                        disabled={busy}
                      >
                        复制
                      </Button>
                    </div>
                  </div>
                ) : null}
                <Input
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  placeholder="输入激活码 da-xxxxxxxx"
                  disabled={busy}
                  autoFocus
                  aria-label="激活码"
                  className="font-mono"
                />
                <Button type="submit" disabled={busy || !token.trim()}>
                  {status === "verifying" ? "验证中…" : "解锁"}
                </Button>
              </form>
            )}

            {status === "error" && (
              <div className="flex w-full flex-col items-center gap-4">
                {errorMessage ? (
                  <p
                    role="alert"
                    className={cn(
                      "max-w-xs text-center text-[length:var(--text-sm)]",
                      "text-muted-foreground",
                    )}
                  >
                    {errorMessage}
                  </p>
                ) : null}
                <Button variant="secondary" onClick={retry}>
                  重试
                </Button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
