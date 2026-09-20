/**
 * 状态徽标样式。
 *
 * 职责：
 *   集中状态徽标（badge）的 Tailwind 类串 —— 与后端 DTO 的 `badge_class` 字段同形状。
 *
 * 设计说明：
 *   - 这几个类串原先散在多个文件里重复出现（状态徽标、事件归约、运行阶段各写一份），
 *     改一次配色要改好几处。收敛到这里之后，语义名（neutral / active / ready / pending /
 *     failed）比色号更好读，也避免了「同一个绿在 A 文件是 emerald-600、在 B 文件写成
 *     emerald-500」这类漂移。
 *   - **后端下发的 `badge_class` 不经过这里** —— 那是服务端的判断，前端只在自己的
 *     兜底默认值上用它。两边形状一致（都是同一个类串），但来源不同，不要混。
 */

export const STATUS_TONE = {
  /** 中性：待命、未知。 */
  neutral: "bg-muted text-muted-foreground",
  /** 进行中：执行中。 */
  active: "bg-sky-500/15 text-sky-700",
  /** 就绪 / 已完成。 */
  ready: "bg-emerald-500/15 text-emerald-600",
  /** 待处理：待登录、待配置。 */
  pending: "bg-amber-500/15 text-amber-700",
  /** 浏览器直播中 —— 与 active 刻意区分：active 是「系统在跑」，live 是「正在替你操作页面」。 */
  live: "bg-rose-500/15 text-rose-600",
  /** 失败。 */
  failed: "bg-red-500/15 text-red-700",
} as const;
