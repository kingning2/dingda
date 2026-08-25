/**
 * License 闸门控制器。
 *
 * 负责：
 * - 拉取授权状态
 * - 判断是否未激活（供侧栏入口等使用，不再全屏拦截）
 * - 将未知错误规范为可读消息
 *
 * @author coisini
 * @created 2026-07-16
 */

import {
  licenseStatus,
  type LicenseStatus,
} from "@desk/platform/ipc/license";

/**
 * 闸门查询结果。
 *
 * @author coisini
 * @created 2026-07-16
 */
export interface LicenseGateSnapshot {
  /** 最新状态；拉取失败时为 `null`。 */
  status: LicenseStatus | null;
  /** 错误消息；成功时为 `null`。 */
  error: string | null;
  /** 有锁且未激活时为 `true`（不再阻断整 app，仅用于 UI 提示）。 */
  gateBlocks: boolean;
}

/**
 * 封装授权闸门查询逻辑（无 React 依赖）。
 *
 * @author coisini
 * @created 2026-07-16
 */
export class LicenseGateController {
  /**
   * 构造闸门控制器。
   *
   * @author coisini
   * @created 2026-07-16
   */
  public constructor() {}

  /**
   * 拉取授权状态并计算是否拦截主界面。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @returns 闸门快照
   */
  public async fetchSnapshot(): Promise<LicenseGateSnapshot> {
    try {
      const status = await licenseStatus();
      return {
        status,
        error: null,
        gateBlocks: this.shouldBlock(status),
      };
    } catch (error: unknown) {
      return {
        status: null,
        error: this.toErrorMessage(error),
        gateBlocks: false,
      };
    }
  }

  /**
   * 判断状态是否应遮罩主界面。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @param status - 授权状态
   * @returns 有锁且未激活时返回 `true`
   */
  public shouldBlock(status: LicenseStatus): boolean {
    return status.gateEnabled && !status.activated;
  }

  /**
   * 将未知错误转为可读字符串。
   *
   * @author coisini
   * @created 2026-07-16
   *
   * @param error - 捕获到的未知错误
   * @returns 人类可读消息
   */
  private toErrorMessage(error: unknown): string {
    if (error instanceof Error) {
      return error.message;
    }
    return String(error);
  }
}
