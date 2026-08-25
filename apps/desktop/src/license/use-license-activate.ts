/**
 * License 激活面板 React Hook（薄适配层）。
 *
 * 将 [`LicenseActivationService`] 接到表单状态，并用 toast 反馈每次操作。
 *
 * @author coisini
 * @created 2026-07-16
 */

import { useEffect, useState } from "react";
import { toast } from "@desk/ui";
import { LicenseActivationService } from "./license-activation-service";

/** 成功后再刷新闸门的短暂延迟（毫秒）。 */
const SUCCESS_DELAY_MS = 900;

/**
 * Hook 返回值：激活表单状态与操作。
 *
 * @author coisini
 * @created 2026-07-16
 */
export interface UseLicenseActivateResult {
  /** 设备码展示值。 */
  machineCode: string;
  /** 当前 token 输入。 */
  token: string;
  /** 更新 token。 */
  setToken: (value: string) => void;
  /** 是否正在激活。 */
  busy: boolean;
  /** 提示/错误消息。 */
  message: string | null;
  /** 复制设备码。 */
  copyMachineCode: () => Promise<void>;
  /** 用 token 激活。 */
  activateWithToken: () => Promise<void>;
}

/**
 * 等待指定毫秒；尊重 `prefers-reduced-motion` 时几乎立即返回。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @param ms - 正常等待时长
 * @returns 无
 */
function waitForDelay(ms: number): Promise<void> {
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return new Promise((resolve) => {
    window.setTimeout(resolve, reduced ? 80 : ms);
  });
}

/**
 * 管理激活面板交互。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @param onActivated - 激活成功后的回调（通常用于刷新闸门）
 * @returns 面板绑定所需状态与方法
 */
export function useLicenseActivate(
  onActivated: () => void,
): UseLicenseActivateResult {
  const [service] = useState(() => new LicenseActivationService());
  const [machineCode, setMachineCode] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void service
      .loadMachineCode()
      .then((code) => {
        if (!cancelled) setMachineCode(code);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const text = error instanceof Error ? error.message : String(error);
        setMessage(text);
        toast.error(text);
      });
    return () => {
      cancelled = true;
    };
  }, [service]);

  async function copyMachineCode() {
    const nextMessage = await service.copyMachineCode();
    setMessage(nextMessage);
    if (nextMessage === "设备码已复制") {
      toast.success(nextMessage);
    } else {
      toast.error(nextMessage);
    }
  }

  async function runActivate(
    run: () => ReturnType<LicenseActivationService["activateWithToken"]>,
  ) {
    const pending = "正在校验激活码…";
    setBusy(true);
    setMessage(pending);
    const toastId = toast.loading(pending);
    const result = await run();
    setMessage(result.message);
    setBusy(false);

    if (result.ok) {
      toast.success(result.message, { id: toastId });
      await waitForDelay(SUCCESS_DELAY_MS);
      onActivated();
      return;
    }

    toast.error(result.message, { id: toastId });
  }

  async function activateWithToken() {
    await runActivate(() => service.activateWithToken(token));
  }

  return {
    machineCode,
    token,
    setToken,
    busy,
    message,
    copyMachineCode,
    activateWithToken,
  };
}
