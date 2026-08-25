/**
 * 将授权过期时间格式化为剩余时长文案。
 *
 * @author coisini
 * @created 2026-07-16
 */

/**
 * 剩余时长展示结果。
 *
 * @author coisini
 * @created 2026-07-16
 */
export interface LicenseRemainingLabel {
  /** 主文案，如「剩余 30 天」。 */
  text: string;
  /** 是否已过期。 */
  expired: boolean;
  /** 是否即将到期（不足 1 天）。 */
  urgent: boolean;
}

/**
 * 根据 Unix 秒级过期时间计算剩余时长文案。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @param expiresAt - 过期时间（Unix 秒）
 * @param nowSec - 当前时间（Unix 秒），默认取浏览器当前时间
 * @returns 展示文案；无效输入时返回 `null`
 */
export function formatLicenseRemaining(
  expiresAt: number,
  nowSec = Math.floor(Date.now() / 1000),
): LicenseRemainingLabel | null {
  if (!Number.isFinite(expiresAt) || expiresAt <= 0) {
    return null;
  }

  const diff = expiresAt - nowSec;
  if (diff <= 0) {
    return { text: "套餐已过期", expired: true, urgent: true };
  }

  const days = Math.floor(diff / 86_400);
  const hours = Math.floor((diff % 86_400) / 3_600);
  const minutes = Math.floor((diff % 3_600) / 60);

  if (days >= 1) {
    return {
      text: `剩余 ${days} 天`,
      expired: false,
      urgent: days < 7,
    };
  }
  if (hours >= 1) {
    return {
      text: `剩余 ${hours} 小时`,
      expired: false,
      urgent: true,
    };
  }
  if (minutes >= 1) {
    return {
      text: `剩余 ${minutes} 分钟`,
      expired: false,
      urgent: true,
    };
  }

  return {
    text: "即将到期",
    expired: false,
    urgent: true,
  };
}

/**
 * 将 Unix 秒格式化为本地到期时间字符串。
 *
 * @author coisini
 * @created 2026-07-16
 *
 * @param expiresAt - 过期时间（Unix 秒）
 * @returns 本地化日期时间
 */
export function formatLicenseExpiresAt(expiresAt: number): string {
  return new Date(expiresAt * 1000).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
