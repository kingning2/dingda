/**
 * 解锁页标题与描述文案 — 状态驱动。
 *
 * @author coisini
 * @created 2026-08-24
 */

import type { UnlockStatus } from "./types";

const STATUS_COPY: Record<UnlockStatus, { title: string; description: string }> = {
  locked: {
    title: "解锁你的工作区",
    description: "输入激活码以验证授权并解锁全部能力。",
  },
  verifying: {
    title: "正在验证授权",
    description: "我们正在校验你的激活码，请稍候。",
  },
  unlocking: {
    title: "正在准备工作区",
    description: "授权验证通过，正在为你启用付费能力。",
  },
  ready: {
    title: "授权已验证",
    description: "工作区已就绪。",
  },
  error: {
    title: "暂时无法解锁",
    description: "我们无法验证你的授权，请检查激活码后重试。",
  },
};

export interface UnlockStatusProps {
  status: UnlockStatus;
}

/**
 * 状态标题 + 描述。
 *
 * @author coisini
 * @created 2026-08-24
 *
 * @param props.status - 当前流程状态
 */
export function UnlockStatus({ status }: UnlockStatusProps) {
  const copy = STATUS_COPY[status];

  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <h1 className="text-[length:var(--text-xl)] font-semibold tracking-tight text-foreground">
        {copy.title}
      </h1>
      <p className="max-w-sm text-[length:var(--text-sm)] leading-relaxed text-muted-foreground">
        {copy.description}
      </p>
    </div>
  );
}
