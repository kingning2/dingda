/** 账号同步发现登录过期时，弹出右上角提示（去扫码登录）。 */

import type { AccountListItem } from "@v2/contracts/account";
import { pushAppAlert } from "@v2/runtime/app-alert";
import { paths } from "@v2/routes/paths";

const PLATFORM_LABEL: Record<string, string> = {
  xianyu: "闲鱼",
  ali1688: "1688",
  xiaohongshu: "小红书",
};

/** 同一账号过期提示冷却，避免 30s 轮询刷屏。 */
const NOTIFY_COOLDOWN_MS = 10 * 60 * 1000;

const notifiedAt = new Map<string, number>();

function isAuthExpired(account: AccountListItem): boolean {
  return account.session.state === "auth_expired";
}

/**
 * 对比刷新前后账号列表：新出现的登录过期账号弹出提示。
 * 已恢复的账号清除冷却，便于下次再次过期时提醒。
 */
export function notifyNewlyExpiredAccounts(
  previous: AccountListItem[],
  next: AccountListItem[],
): void {
  const prevById = new Map(previous.map((item) => [item.account_id, item]));
  const now = Date.now();

  for (const account of next) {
    if (!isAuthExpired(account)) {
      notifiedAt.delete(account.account_id);
      continue;
    }

    const prev = prevById.get(account.account_id);
    const newlyExpired = !prev || !isAuthExpired(prev);
    if (!newlyExpired) continue;

    const last = notifiedAt.get(account.account_id);
    if (last !== undefined && now - last < NOTIFY_COOLDOWN_MS) continue;

    notifiedAt.set(account.account_id, now);

    const platform = PLATFORM_LABEL[account.platform] ?? account.platform;
    const name = account.display_name.trim() || account.account_id;

    pushAppAlert({
      title: `${platform}账号需重新登录`,
      description: `「${name}」登录态已过期，请重新扫码登录`,
      variant: "destructive",
      action: {
        label: "去登录",
        href: `${paths.accounts}?platform=${encodeURIComponent(account.platform)}`,
      },
    });
  }
}
