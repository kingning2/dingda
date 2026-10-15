/**
 * 状态徽标的语义配色（全前端唯一来源）。
 *
 * 职责：
 *   把「状态 → Tailwind 类串」收在一处；组件直接消费，不再自拼色号。
 *
 * 设计说明：
 *   - 色值定义在 ui-theme 的 `@theme`（`--color-tone-*`），这里只选语义名；
 *     改配色改 theme 一处即可，不会出现「同一个绿在 A 文件 emerald-600、
 *     在 B 文件写成 emerald-500」的漂移。
 *   - 后端**不下发**样式（`badge_class` 已从线协议删除——Tailwind 类串跨栈耦合），
 *     各域用自己的 `state` 字段映射到这里。
 *   - neutral 不设独立色：未安装/未知直接用 muted 语义令牌。
 */

export const STATUS_TONE = {
  /** 中性：未安装、待命、未知、未连接。 */
  neutral: "bg-muted text-muted-foreground",
  /** 进行中：探测中、执行中、已售出（信息蓝）。 */
  active: "bg-tone-active/15 text-tone-active",
  /** 就绪 / 已完成 / 在卖 / 降价。 */
  ready: "bg-tone-ready/15 text-tone-ready",
  /** 待处理：待登录、待配置、已暂停、已下架。 */
  pending: "bg-tone-pending/15 text-tone-pending",
  /** 浏览器直播中 / 涨价 —— 与 active 刻意区分：active 是「系统在跑」，live 是「正在替你操作页面」。 */
  live: "bg-tone-live/15 text-tone-live",
  /** 失败 / 取不到。 */
  failed: "bg-tone-failed/15 text-tone-failed",
} as const;
