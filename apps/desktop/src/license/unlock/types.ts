/**
 * License 解锁页共享类型。

 * @author coisini
 * @created 2026-08-24
 */

/** 解锁流程状态。 */
export type UnlockStatus = "locked" | "verifying" | "unlocking" | "ready" | "error";

/** 单个校验步骤的展示状态。 */
export type UnlockStepState = "pending" | "active" | "done";

/** 校验步骤描述。 */
export interface UnlockStep {
  /** 步骤唯一 id。 */
  id: string;
  /** 展示文案。 */
  label: string;
  /** 当前状态。 */
  state: UnlockStepState;
}
