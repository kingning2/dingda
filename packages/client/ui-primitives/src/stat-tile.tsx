/**
 * 指标块：一个名称配一个值，放在 `<dl>` 里成组。
 *
 * 职责：
 *     监控详情的 6 个快照指标、账号个人主页的 5 个统计项 —— 同一种小方块，
 *     原先一处在 `monitor-detail.tsx` 的本地组件里、一处在 `accounts-panel.tsx` 里手写了五遍。
 *
 * 设计说明：
 *     - 渲染 `<dt>` / `<dd>`，所以**必须放在 `<dl>` 里**（调用方的栅格容器就是那个 `<dl>`）。
 *       「名称-值」对本来就是描述列表，之前用 `<div>` 包是随手写的，不是有意的选择。
 *     - 带极浅底色与描边，是为了在一堆 `<dd>` 数值里给每格一个可见的边界；外观照搬
 *       `monitor-detail.tsx` 已被 6 处使用验证过的那版（原先账号侧那 5 个没有底色）。
 */

interface StatTileProps {
  label: string;
  value: string;
}

/** 单个指标：名称 + 值。 */
export function StatTile({ label, value }: StatTileProps) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}
