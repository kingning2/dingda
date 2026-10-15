/**
 * 可加入监控的平台词表。
 *
 * 职责：
 *     定义表单可选的平台，并把平台 id 翻成显示名。
 *
 * 设计说明：
 *     词表放前端而不从后端拉：后端 `POST /v1/watch/targets` 的 `platform` 是自由字符串
 *     （采集侧按平台注册表分发），这里给的是「已知能被轮询的」三个选项。
 *     未收录的平台**原样回显**，不吞成「未知」—— 排障时看到原始值比看到兜底文案有用。
 */

/** 监控页可选的平台。 */
export const MONITOR_PLATFORMS = [
  { id: "xianyu", label: "闲鱼" },
  { id: "ali1688", label: "1688" },
  { id: "xiaohongshu", label: "小红书" },
] as const;

/** 平台 id → 显示名；未收录的平台原样返回。 */
export function platformLabel(platform: string): string {
  return MONITOR_PLATFORMS.find((item) => item.id === platform)?.label ?? platform;
}
