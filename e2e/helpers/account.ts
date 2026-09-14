/**
 * 账号 / 扫码流程的测试侧辅助。
 *
 * 这些请求跑在**测试进程（Node）**里，直连被测壳拉起的 Python Server，
 * 用途只有两个：
 *   1. 扫码**前**独立判定账号是否有效（决定要不要扫码）；
 *   2. 扫码**后**独立校验结果，不依赖前端自报。
 *
 * 注意：绝不使用它们推进扫码流程本身 —— 那必须点页面按钮。
 * 见 specs/account-qr.spec.ts 的「驱动原则」。
 */

export type AccountPlatform = "xianyu" | "ali1688" | "xiaohongshu";

/** 平台中文名：用于定位页签（`<中文名>账号`）与日志。 */
export const PLATFORM_LABEL: Record<AccountPlatform, string> = {
  xianyu: "闲鱼",
  ali1688: "1688",
  xiaohongshu: "小红书",
};

export type AccountRecord = {
  account_id: string;
  platform: AccountPlatform;
  display_name: string;
  auth_valid: boolean;
  session: { state: string; label: string; hint: string | null };
};

/**
 * 读账号列表。
 *
 * `auth_valid` 是**落库的字段**（`domains/account/persist.py` 扫码成功时写 True），
 * 不是前端派生值，所以可以放心当作「登录态是否有效」的判据。
 */
export async function fetchAccounts(
  port: number,
  platform?: AccountPlatform,
  timeoutMs = 8_000,
): Promise<AccountRecord[]> {
  const query = platform ? `?platform=${platform}` : "";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://127.0.0.1:${port}/v1/accounts${query}`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`GET /v1/accounts 返回 HTTP ${response.status}`);
    }
    const payload = (await response.json()) as { items?: AccountRecord[] };
    return payload.items ?? [];
  } finally {
    clearTimeout(timer);
  }
}

/** 该平台下有效账号数量。 */
export function countValid(items: AccountRecord[], platform: AccountPlatform): number {
  return items.filter((item) => item.platform === platform && item.auth_valid).length;
}

/** 一行摘要，便于日志里看清「有几个账号、什么状态」。 */
export function describeAccounts(
  items: AccountRecord[],
  platform: AccountPlatform,
): string {
  const scoped = items.filter((item) => item.platform === platform);
  if (scoped.length === 0) return "无账号";
  return scoped
    .map(
      (item) =>
        `${item.display_name}(${item.account_id}) auth_valid=${item.auth_valid} state=${item.session.state}`,
    )
    .join("；");
}
