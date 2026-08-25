/**
 * License 激活业务服务。
 *
 * 负责：
 * - 加载并复制设备码
 * - Token 激活
 *
 * @author coisini
 * @created 2026-07-16
 */

import {
  licenseActivate,
  licenseMachineCode,
  type LicenseStatus,
} from "@desk/platform/ipc/license";

/**
 * 激活操作结果。
 *
 * @author coisini
 * @created 2026-07-16
 */
export interface LicenseActivationResult {
  /** 是否激活成功。 */
  ok: boolean;
  /** UI 提示文案。 */
  message: string;
  /** 后端返回的状态（失败时可能仍有部分字段）。 */
  status: LicenseStatus | null;
}

/**
 * 有状态的激活流程服务（不依赖 React）。
 *
 * @author coisini
 * @created 2026-07-16
 */
export class LicenseActivationService {
  private machineCodeValue = "";

  /**
   * 构造激活服务。
   *
   * @author coisini
   * @created 2026-07-16
   */
  public constructor() {}

  /**
   * 当前缓存的设备码。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @returns 设备码字符串，未加载时为空串
   */
  public get machineCode(): string {
    return this.machineCodeValue;
  }

  /**
   * 从后端加载本机设备码并缓存。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @returns 设备码
   * @throws 当 IPC 失败时抛出错误
   */
  public async loadMachineCode(): Promise<string> {
    const code = await licenseMachineCode();
    this.machineCodeValue = code;
    return code;
  }

  /**
   * 将设备码写入剪贴板。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @returns 成功或失败的提示文案
   */
  public async copyMachineCode(): Promise<string> {
    if (!this.machineCodeValue) {
      return "设备码尚未加载";
    }
    try {
      await navigator.clipboard.writeText(this.machineCodeValue);
      return "设备码已复制";
    } catch (error: unknown) {
      console.error("复制设备码失败", {
        machineCodeLength: this.machineCodeValue.length,
        error,
      });
      return "复制失败，请手动选择";
    }
  }

  /**
   * 使用粘贴的 token 激活。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @param token - 激活 token 原文
   * @returns 激活结果
   */
  public async activateWithToken(token: string): Promise<LicenseActivationResult> {
    return this.runActivation(() =>
      licenseActivate({ token: token.trim() }),
    );
  }

  /**
   * 统一执行激活并规范化成功/失败消息。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @param invokeActivate - 实际 IPC 调用
   * @returns 激活结果
   */
  private async runActivation(
    invokeActivate: () => Promise<LicenseStatus>,
  ): Promise<LicenseActivationResult> {
    try {
      const status = await invokeActivate();
      if (!status.activated) {
        return {
          ok: false,
          message: status.reason ?? "激活失败",
          status,
        };
      }
      return {
        ok: true,
        message: "激活成功",
        status,
      };
    } catch (error: unknown) {
      console.error("license 激活失败", { error });
      return {
        ok: false,
        message: error instanceof Error ? error.message : String(error),
        status: null,
      };
    }
  }
}
